import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
TIMING_DIR = ROOT / "models" / "timing"

STEP = 15
EVENTS = ("high180", "high140")
BATCH_SIZE = 1000
TOLERANCE = 1e-4

columns = json.loads(
    (DATA_DIR / "columns.json").read_text(encoding="utf-8")
)

deployment_meta = json.loads(
    (ROOT / "models" / "meta.json").read_text(encoding="utf-8")
)

features = deployment_meta["features"]
data = pd.read_parquet(DATA_DIR / "glucose_15min.parquet")

data["last_meal_type"] = pd.Categorical(
    data["last_meal_type"],
    categories=["none", "breakfast", "lunch", "dinner", "snack"],
)


def check_event(event):
    print(f"\n{'=' * 65}")
    print(f"Checking deployed timing inference: {event}")
    print(f"{'=' * 65}")

    oof_path = DATA_DIR / f"oof_surv_{event}_none.parquet"
    meta_path = TIMING_DIR / f"{event}.meta.json"

    if not oof_path.exists():
        raise FileNotFoundError(
            f"Missing OOF file: {oof_path}. "
            f"Run src/survival.py {event} first."
        )

    if not meta_path.exists():
        raise FileNotFoundError(
            f"Missing timing metadata: {meta_path}"
        )

    metadata = json.loads(
        meta_path.read_text(encoding="utf-8")
    )

    if metadata["features"] != features:
        raise ValueError(
            f"{event}: timing feature order differs from deployment metadata."
        )

    d = (
        data[data[f"{event}_usable"] == 1]
        .copy()
        .reset_index(drop=True)
    )

    oof = pd.read_parquet(oof_path)

    keys = ["subject", "timestamp", "fold"]
    risk_columns = [
        f"risk_{h}"
        for h in range(STEP, metadata["max_minutes"] + 1, STEP)
    ]

    required_oof = set(keys + risk_columns)
    missing = required_oof - set(oof.columns)

    if missing:
        raise ValueError(
            f"{event}: OOF file missing columns: {sorted(missing)}"
        )

    # Match each dataset anchor with its held-out OOF result.
    anchors = d[keys].copy()
    anchors["_row"] = np.arange(len(anchors))

    matched = anchors.merge(
        oof[keys + risk_columns],
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
        sort=False,
    ).sort_values("_row")

    unmatched = int((matched["_merge"] != "both").sum())

    if unmatched:
        raise ValueError(
            f"{event}: {unmatched} anchors did not match the OOF file."
        )

    reference = matched[risk_columns].to_numpy(dtype=float)

    # Prepare features with the same categories and column order
    # used by the deployed timing model.
    Xd = d[features].copy()

    for col in features:
        if col != "last_meal_type":
            Xd[col] = Xd[col].astype("float32")

    periods = np.arange(
        STEP,
        metadata["max_minutes"] + 1,
        STEP,
        dtype=np.float32,
    )

    K = len(periods)
    predicted = np.full((len(d), K), np.nan, dtype=float)

    fold_values = d["fold"].to_numpy()

    for fold in sorted(np.unique(fold_values)):
        fold = int(fold)
        indices = np.flatnonzero(fold_values == fold)

        model_path = TIMING_DIR / f"fold{fold}" / f"{event}.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"Missing fold-specific model: {model_path}"
            )

        model = xgb.XGBClassifier(enable_categorical=True)
        model.load_model(str(model_path))

        print(
            f"fold{fold}: checking {len(indices):,} held-out anchors"
        )

        for start in range(0, len(indices), BATCH_SIZE):
            batch = indices[start:start + BATCH_SIZE]
            count = len(batch)

            # Each anchor is expanded across all future intervals.
            X = Xd.iloc[np.repeat(batch, K)].reset_index(drop=True)
            X["k_min"] = np.tile(periods, count)
            X = X[metadata["model_features"]]

            hazards = np.clip(
                model.predict_proba(X)[:, 1].reshape(count, K),
                0.0,
                1.0,
            )

            cumulative = 1.0 - np.cumprod(
                1.0 - hazards,
                axis=1,
            )

            predicted[batch] = cumulative

    differences = np.abs(predicted - reference)

    if not np.isfinite(differences).all():
        raise ValueError(
            f"{event}: comparison produced non-finite differences."
        )

    max_diff = float(differences.max())
    mean_diff = float(differences.mean())
    mismatch_count = int(
        (differences > TOLERANCE).sum()
    )

    print(f"\nAnchors compared: {len(d):,}")
    print(f"Horizons per anchor: {K}")
    print(f"Mean absolute probability difference: {mean_diff:.8f}")
    print(f"Maximum absolute probability difference: {max_diff:.8f}")
    print(
        f"Values differing by more than {TOLERANCE}: "
        f"{mismatch_count:,} / {differences.size:,}"
    )

    # Show error by horizon to identify systematic differences.
    per_horizon = pd.DataFrame({
        "horizon_min": periods.astype(int),
        "mean_abs_diff": differences.mean(axis=0),
        "max_abs_diff": differences.max(axis=0),
    })

    print("\nDifferences by horizon:")
    print(per_horizon.to_string(index=False, float_format=lambda x: f"{x:.8f}"))

    ok = max_diff <= TOLERANCE

    print(f"\n{event} inference parity:", "PASS" if ok else "CHECK")

    return ok


def main():
    results = {}

    for event in EVENTS:
        results[event] = check_event(event)

    print(f"\n{'=' * 65}")
    print("FINAL RESULT:", "PASS" if all(results.values()) else "CHECK")
    print(f"{'=' * 65}")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()