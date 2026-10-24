import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "models" / "timing"

STEP = 15
EVENTS_TO_TRAIN = ("high180", "high140")
MEAL_TYPES = ["none", "breakfast", "lunch", "dinner", "snack"]

columns = json.loads(
    (DATA_DIR / "columns.json").read_text(encoding="utf-8")
)
model_meta = json.loads(
    (ROOT / "models" / "meta.json").read_text(encoding="utf-8")
)

groups = columns["groups"]

# Keep the same feature construction as src/survival.py.
features = list(
    dict.fromkeys(
        groups["glucose"]
        + groups["wearable"]
        + groups["meals"]
        + groups["time"]
    )
)

# Ensure feature order matches the deployed risk models.
deployment_features = model_meta["features"]

if features != deployment_features:
    raise ValueError(
        "Timing feature order differs from models/meta.json. "
        "Resolve the feature mismatch before training."
    )

data_path = DATA_DIR / "glucose_15min.parquet"
data = pd.read_parquet(data_path)

data["last_meal_type"] = pd.Categorical(
    data["last_meal_type"],
    categories=MEAL_TYPES,
)

if "fold" not in data.columns:
    raise ValueError("Training table has no participant fold column.")

folds = sorted(data["fold"].dropna().unique().astype(int))

if len(folds) < 2:
    raise ValueError("At least two participant folds are required.")

MODEL_DIR.mkdir(parents=True, exist_ok=True)


def make_model():
    return xgb.XGBClassifier(
        n_estimators=300,
        learning_rate=0.06,
        max_depth=5,
        min_child_weight=50,
        subsample=0.7,
        colsample_bytree=0.8,
        reg_lambda=10.0,
        tree_method="hist",
        enable_categorical=True,
        eval_metric="logloss",
        n_jobs=-1,
        random_state=0,
    )


def train_event(event):
    print(f"\n{'=' * 60}")
    print(f"Training timing models: {event}")
    print(f"{'=' * 60}")

    if event not in columns["events"]:
        raise ValueError(f"Unknown event: {event}")

    required = [
        "subject",
        "fold",
        *features,
        f"{event}_usable",
        f"{event}_event",
        f"{event}_follow",
        f"{event}_tte",
    ]

    missing = set(required) - set(data.columns)

    if missing:
        raise ValueError(
            f"{event}: missing columns: {sorted(missing)}"
        )

    d = (
        data[data[f"{event}_usable"] == 1]
        .copy()
        .reset_index(drop=True)
    )

    if d.empty:
        raise ValueError(f"{event}: no usable training rows.")

    Xd = d[features].copy()

    numeric_features = [
        name for name in features
        if name != "last_meal_type"
    ]

    Xd[numeric_features] = Xd[numeric_features].astype("float32")

    has_event = d[f"{event}_event"].to_numpy().astype(bool)

    follow = d[f"{event}_follow"].to_numpy(dtype=float)

    if not np.isfinite(follow).all():
        raise ValueError(
            f"{event}: follow-up contains invalid values."
        )

    follow_steps = np.floor(follow / STEP).astype(int)
    follow_steps = np.maximum(follow_steps, 0)

    tte = d[f"{event}_tte"].to_numpy(dtype=float)

    event_step = np.where(
        has_event & np.isfinite(tte),
        np.floor(np.nan_to_num(tte, nan=0.0) / STEP),
        0,
    ).astype(int)

    event_step = np.maximum(event_step, 0)

    horizon_steps = len(columns["future_horizons"])
    max_minutes = horizon_steps * STEP

    def expand(anchor_idx):
        # Build one row for every observed at-risk interval.
        lengths = np.where(
            has_event[anchor_idx],
            np.minimum(
                event_step[anchor_idx],
                follow_steps[anchor_idx],
            ),
            follow_steps[anchor_idx],
        )

        lengths = np.maximum(lengths, 0)

        keep = lengths > 0
        anchor_idx = anchor_idx[keep]
        lengths = lengths[keep]

        if not len(anchor_idx):
            raise ValueError("No person-period rows were generated.")

        rows = np.repeat(anchor_idx, lengths)
        starts = np.cumsum(lengths) - lengths

        periods = (
            np.arange(int(lengths.sum()))
            - np.repeat(starts, lengths)
            + 1
        )

        X = Xd.iloc[rows].reset_index(drop=True)

        X["k_min"] = (
            periods * STEP
        ).astype("float32")

        y = (
            has_event[rows]
            & (periods == event_step[rows])
        ).astype(np.int8)

        return X, y

    def fit_subset(anchor_idx, description):
        start = time.time()

        X, y = expand(anchor_idx)

        if np.unique(y).size != 2:
            raise ValueError(
                f"{event} {description}: training data must contain "
                "both event and non-event intervals."
            )

        model = make_model()
        model.fit(X, y)

        print(
            f"{description}: anchors={len(anchor_idx):,} | "
            f"person-period rows={len(X):,} | "
            f"event intervals={int(y.sum()):,} | "
            f"time={time.time() - start:.1f}s"
        )

        return model, int(len(X)), int(y.sum())

    # -----------------------------------------------------
    # Full-data model for new patients.
    # -----------------------------------------------------
    all_idx = np.arange(len(d))

    final_model, final_rows, final_events = fit_subset(
        all_idx,
        "final model",
    )

    final_path = MODEL_DIR / f"{event}.json"
    final_model.save_model(str(final_path))

    # -----------------------------------------------------
    # Fold models for participant-held-out replay.
    # A fold model never trains on anchors belonging to
    # the same held-out fold.
    # -----------------------------------------------------
    fold_info = {}

    fold_values = d["fold"].to_numpy()

    for fold in folds:
        train_idx = np.flatnonzero(fold_values != fold)

        if len(train_idx) == 0:
            raise ValueError(
                f"{event}: no training anchors for fold {fold}."
            )

        fold_model, person_rows, event_rows = fit_subset(
            train_idx,
            f"fold{fold}",
        )

        fold_dir = MODEL_DIR / f"fold{fold}"
        fold_dir.mkdir(parents=True, exist_ok=True)

        fold_path = fold_dir / f"{event}.json"
        fold_model.save_model(str(fold_path))

        fold_info[str(fold)] = {
            "model_path": f"fold{fold}/{event}.json",
            "training_anchors": int(len(train_idx)),
            "person_period_rows": person_rows,
            "event_intervals": event_rows,
        }

    # Save common inference metadata for this task.
    event_spec = columns["events"][event]

    metadata = {
        "event": event,
        "kind": "discrete_time_hazard",
        "threshold": event_spec["threshold"],
        "direction": event_spec["direction"],
        "step_minutes": STEP,
        "max_minutes": max_minutes,
        "features": features,
        "model_features": features + ["k_min"],
        "categorical_features": (
            ["last_meal_type"]
            if "last_meal_type" in features
            else []
        ),
        "meal_types": MEAL_TYPES,
        "final_model": f"{event}.json",
        "final_training_anchors": int(len(d)),
        "final_person_period_rows": final_rows,
        "final_event_intervals": final_events,
        "fold_of_subject": model_meta["fold_of_subject"],
        "fold_models": fold_info,
        "risk_interpretation": (
            "Cumulative probability of the configured threshold "
            "event within the forecast horizon."
        ),
        "timing_interpretation": (
            "Estimated event-time distribution conditional on an "
            "event occurring within the model horizon. Not a "
            "guaranteed crossing time."
        ),
    }

    meta_path = MODEL_DIR / f"{event}.meta.json"

    meta_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(f"Final model: {final_path}")
    print(f"Metadata: {meta_path}")
    print(f"Fold models saved: {len(fold_info)}")


def main():
    start = time.time()

    for event in EVENTS_TO_TRAIN:
        train_event(event)

    print(f"\nAll timing models completed in {time.time() - start:.1f}s.")
    print(f"Model directory: {MODEL_DIR}")


if __name__ == "__main__":
    main()