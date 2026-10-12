"""
Train final Glucose Twin models and generate held-out OOF predictions.

Run from the project root:
    python src\train_model.py

Creates:
    models/final/          Final models trained on all eligible participants
    models/fold0..fold4/   Models trained without the corresponding fold
    models/meta.json       Model and feature metadata
    data/processed/oof_<event>.parquet
    data/processed/train_oof_metrics.csv
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)

warnings.filterwarnings("ignore")

OUT = Path("data/processed")
MODELS = Path("models")
FINAL = MODELS / "final"

EVENTS = ["high180", "high140", "low70"]
MEAL_TYPES = ["none", "breakfast", "lunch", "dinner", "snack"]

THRESHOLDS = {
    "high180": {"sensitive": 0.30, "balanced": 0.50},
    "high140": {"sensitive": 0.40, "balanced": 0.50},
    "low70": {"sensitive": 0.30, "balanced": 0.50},
}

meta = json.loads((OUT / "columns.json").read_text())
G = meta["groups"]
HORIZONS = list(meta["risk_horizons"])

FEATURES = list(dict.fromkeys(
    G["glucose"] + G["wearable"] + G["meals"] + G["time"]
))
CATEGORICAL = [
    c for c in meta.get("categorical", [])
    if c in FEATURES
]

data = pd.read_parquet(
    OUT / "glucose_15min.parquet"
).reset_index(drop=True)

missing = [c for c in FEATURES if c not in data.columns]
if missing:
    raise SystemExit(f"Missing feature columns: {missing}")

for event in EVENTS:
    if event not in meta["events"]:
        raise SystemExit(f"Event missing from metadata: {event}")
    for suffix in ["usable"] + [f"within_{h}" for h in HORIZONS]:
        col = f"{event}_{suffix}"
        if col not in data.columns:
            raise SystemExit(f"Missing target column: {col}")

if "last_meal_type" in CATEGORICAL:
    data["last_meal_type"] = pd.Categorical(
        data["last_meal_type"],
        categories=MEAL_TYPES,
    )

data["fold"] = pd.to_numeric(
    data["fold"], errors="raise"
).astype(int)

subject_fold_count = data.groupby("subject")["fold"].nunique()
if (subject_fold_count > 1).any():
    raise SystemExit(
        "Leakage check failed: a participant appears in multiple folds."
    )

FOLDS = sorted(data["fold"].unique().tolist())

X = data[FEATURES].copy()

for col in FEATURES:
    if col == "last_meal_type":
        X[col] = pd.Categorical(
            X[col], categories=MEAL_TYPES
        )
    elif col not in CATEGORICAL:
        X[col] = pd.to_numeric(
            X[col], errors="coerce"
        ).astype("float32")
        X[col] = X[col].replace(
            [np.inf, -np.inf], np.nan
        )

MODELS.mkdir(parents=True, exist_ok=True)
FINAL.mkdir(parents=True, exist_ok=True)

print(
    f"Participants: {data['subject'].nunique()} | "
    f"Rows: {len(data):,} | Features: {len(FEATURES)} | "
    f"Folds: {FOLDS}"
)
print(f"Horizons: {HORIZONS}")
print("Feature strategy: CGM + wearable + logged meals + time; no EHR")


def make_model():
    return xgb.XGBClassifier(
        n_estimators=250,
        learning_rate=0.05,
        max_depth=4,
        min_child_weight=20,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=5.0,
        tree_method="hist",
        enable_categorical=True,
        eval_metric="logloss",
        n_jobs=-1,
        random_state=0,
    )


def fit_and_save(train_mask, target_col, path):
    labels = pd.to_numeric(
        data.loc[train_mask, target_col],
        errors="coerce",
    )
    valid = labels.notna()
    idx = labels.index[valid]
    y = labels.loc[idx].astype(int)

    if len(y) == 0 or y.nunique() < 2:
        raise RuntimeError(
            f"Cannot train {path}: target has fewer than two classes."
        )

    model = make_model()
    model.fit(X.loc[idx, FEATURES], y)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))

    return model, {
        "rows": int(len(y)),
        "positive_labels": int(y.sum()),
        "prevalence": float(y.mean()),
    }


def score_oof(event, horizon, probabilities):
    usable = data[f"{event}_usable"].eq(1)
    y_all = pd.to_numeric(
        data[f"{event}_within_{horizon}"],
        errors="coerce",
    ).to_numpy(dtype=float)

    valid = (
        usable.to_numpy()
        & np.isfinite(y_all)
        & np.isfinite(probabilities)
    )

    y = y_all[valid].astype(int)
    p = probabilities[valid]
    fold = data.loc[valid, "fold"].to_numpy()

    if len(y) == 0:
        return {
            "n": 0, "events": 0, "prevalence": np.nan,
            "auroc": np.nan, "auroc_fold_sd": np.nan,
            "average_precision": np.nan, "brier_skill": np.nan,
        }

    auc = (
        roc_auc_score(y, p)
        if np.unique(y).size == 2
        else np.nan
    )
    ap = (
        average_precision_score(y, p)
        if np.unique(y).size == 2
        else np.nan
    )

    fold_aucs = []
    for f in np.unique(fold):
        m = fold == f
        if np.unique(y[m]).size == 2:
            fold_aucs.append(roc_auc_score(y[m], p[m]))

    prevalence = float(y.mean())
    if 0 < prevalence < 1:
        brier = brier_score_loss(y, p)
        brier_baseline = prevalence * (1 - prevalence)
        bss = 1 - brier / brier_baseline
    else:
        bss = np.nan

    return {
        "n": int(len(y)),
        "events": int(y.sum()),
        "prevalence": prevalence,
        "auroc": float(auc) if np.isfinite(auc) else np.nan,
        "auroc_fold_sd": (
            float(np.std(fold_aucs)) if fold_aucs else np.nan
        ),
        "average_precision": (
            float(ap) if np.isfinite(ap) else np.nan
        ),
        "brier_skill": float(bss) if np.isfinite(bss) else np.nan,
    }


metrics_rows = []
manifest_models = {}

for event in EVENTS:
    print(f"\n=== {event} ===")

    usable = data[f"{event}_usable"].eq(1)
    manifest_models[event] = {}
    oof_by_horizon = {}

    for horizon in HORIZONS:
        target = f"{event}_within_{horizon}"
        predictions = np.full(len(data), np.nan, dtype=float)
        fold_info = {}

        # Fit on four folds; predict the excluded participant fold.
        for f in FOLDS:
            train_mask = usable & data["fold"].ne(f)
            test_mask = usable & data["fold"].eq(f)

            path = MODELS / f"fold{f}" / f"{event}_{horizon}.json"
            model, stats = fit_and_save(
                train_mask, target, path
            )

            test_idx = data.index[test_mask].to_numpy()
            if len(test_idx):
                predictions[test_idx] = model.predict_proba(
                    X.loc[test_idx, FEATURES]
                )[:, 1]

            fold_info[str(f)] = {
                "file": path.as_posix(),
                **stats,
                "held_out_subjects": sorted(
                    data.loc[test_mask, "subject"].unique().tolist()
                ),
            }

        # Final model: train on all eligible participants.
        final_path = FINAL / f"{event}_{horizon}.json"
        _, final_stats = fit_and_save(
            usable, target, final_path
        )

        metrics = score_oof(
            event, horizon, predictions
        )
        metrics_rows.append({
            "event": event,
            "horizon_min": horizon,
            **metrics,
        })

        oof_by_horizon[horizon] = predictions
        manifest_models[event][str(horizon)] = {
            "final": {
                "file": final_path.as_posix(),
                **final_stats,
            },
            "fold_models": fold_info,
            "oof_metrics": metrics,
        }

        auc_text = (
            f"{metrics['auroc']:.3f}"
            if np.isfinite(metrics["auroc"]) else "n/a"
        )
        ap_text = (
            f"{metrics['average_precision']:.3f}"
            if np.isfinite(metrics["average_precision"]) else "n/a"
        )
        print(
            f"  {horizon:>3}m | final rows={final_stats['rows']:,} | "
            f"events={final_stats['positive_labels']:,} | "
            f"OOF AUROC={auc_text} | AP={ap_text}"
        )

    # Write the format expected by alerts.py.
    base_cols = [
        "subject", "timestamp", "fold", "glucose",
        f"{event}_tte", f"{event}_event",
    ] + [f"{event}_within_{h}" for h in HORIZONS]

    oof = data.loc[usable, base_cols].copy()

    row_indices = oof.index.to_numpy()
    for horizon in HORIZONS:
        oof[f"p_noehr_{horizon}"] = oof_by_horizon[horizon][row_indices]

    oof_path = OUT / f"oof_{event}.parquet"
    oof.to_parquet(oof_path, index=False)
    print(f"  Saved OOF predictions: {oof_path}")


metrics_df = pd.DataFrame(metrics_rows)
metrics_path = OUT / "train_oof_metrics.csv"
metrics_df.to_csv(metrics_path, index=False)

fold_of_subject = {
    str(subject): int(fold)
    for subject, fold in data.groupby("subject")["fold"].first().items()
}

manifest = {
    "features": FEATURES,
    "categorical_features": CATEGORICAL,
    "meal_types": MEAL_TYPES,
    "horizons": HORIZONS,
    "events": {e: meta["events"][e] for e in EVENTS},
    "thresholds": THRESHOLDS,
    "folds": FOLDS,
    "fold_of_subject": fold_of_subject,
    "feature_strategy": "dynamic_no_ehr_no_consumed_amounts",
    "model_parameters": {
        "n_estimators": 250,
        "learning_rate": 0.05,
        "max_depth": 4,
        "min_child_weight": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 5.0,
        "tree_method": "hist",
        "enable_categorical": True,
        "eval_metric": "logloss",
        "random_state": 0,
    },
    "models": manifest_models,
    "metrics_file": metrics_path.as_posix(),
    "note": (
        "Fold models produce participant-held-out predictions. Final models are "
        "trained on all eligible rows for deployment. Alert thresholds are exploratory."
    ),
}
(MODELS / "meta.json").write_text(
    json.dumps(manifest, indent=2)
)

# Verify that the saved final model reloads with the expected feature schema.
sample = data[data["high180_usable"].eq(1)].head(5)
if len(sample):
    check = xgb.XGBClassifier(enable_categorical=True)
    check.load_model(str(FINAL / "high180_120.json"))
    sample_idx = sample.index.to_numpy()
    probs = check.predict_proba(X.loc[sample_idx, FEATURES])[:, 1]
    print("\nReload check, high180 120-min risk:", np.round(probs, 3))

print("\n=== POOLED OUT-OF-FOLD METRICS ===")
print(metrics_df.to_string(index=False))
print(f"\nSaved final models: {FINAL}")
print(f"Saved fold models: {MODELS}/fold0 ... {MODELS}/fold{FOLDS[-1]}")
print(f"Saved metadata: {MODELS / 'meta.json'}")
print(f"Saved metrics: {metrics_path}")