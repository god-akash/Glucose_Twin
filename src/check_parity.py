import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.features import PatientState, to_minute


args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
SUBJECT = int(args[0]) if args else 36
SHUFFLE = "--ordered" not in sys.argv
PATIENT_TZ = None

META_PATH = ROOT / "models" / "meta.json"
COLS_PATH = ROOT / "data" / "processed" / "columns.json"
EVENTS_PATH = (
    ROOT
    / "data"
    / "processed"
    / "replay"
    / f"events_{SUBJECT:03d}.parquet"
)
GRID_PATH = ROOT / "data" / "processed" / "glucose_15min.parquet"

for path in (META_PATH, COLS_PATH, EVENTS_PATH, GRID_PATH):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

manifest = json.loads(META_PATH.read_text(encoding="utf-8"))
cols = json.loads(COLS_PATH.read_text(encoding="utf-8"))

events = {
    name: (spec["threshold"], spec["direction"])
    for name, spec in manifest["events"].items()
}

FEATURES = manifest["features"]
CATEGORICAL = set(manifest.get("categorical_features", []))
CATEGORICAL.add("last_meal_type")

event_frame = pd.read_parquet(EVENTS_PATH)
grid = pd.read_parquet(GRID_PATH)

required_event_cols = {
    "kind",
    "timestamp",
    "hr",
    "act_level",
    "activity_calories",
    "value",
    "meal_type",
    "calories",
    "carbs",
    "protein",
    "fat",
    "fiber",
}
missing_cols = required_event_cols - set(event_frame.columns)

if missing_cols:
    raise ValueError(
        f"Event file is missing columns: {sorted(missing_cols)}"
    )

if not {"subject", "timestamp"}.issubset(grid.columns):
    raise ValueError(
        "Training grid must contain 'subject' and 'timestamp'."
    )

grid = grid[grid["subject"] == SUBJECT].copy().reset_index(drop=True)

if grid.empty:
    raise ValueError(
        f"No training-grid rows found for subject {SUBJECT:03d}."
    )

if not FEATURES:
    raise ValueError("No features found in models/meta.json.")


def nz(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def minute(ts):
    return to_minute(ts, PATIENT_TZ)


def build(frame):
    state = PatientState(
        caps=cols["macro_caps"],
        events=events,
        tz=PATIENT_TZ,
    )

    if SHUFFLE:
        order = np.random.default_rng(0).permutation(len(frame))
    else:
        order = np.arange(len(frame))

    for row in frame.iloc[order].itertuples(index=False):
        if row.kind == "wearable":
            state.add_wearable(
                row.timestamp,
                hr=nz(row.hr),
                act=nz(row.act_level),
                cal=nz(row.activity_calories),
            )

        elif row.kind == "glucose":
            state.add_glucose(
                row.timestamp,
                row.value,
            )

        elif row.kind == "meal":
            state.add_meal(
                row.timestamp,
                {
                    "meal_type": row.meal_type,
                    "calories": nz(row.calories),
                    "carbs": nz(row.carbs),
                    "protein": nz(row.protein),
                    "fat": nz(row.fat),
                    "fiber": nz(row.fiber),
                },
            )

        else:
            raise ValueError(
                f"Unknown event kind: {row.kind!r}"
            )

    return state


# ---------------------------------------------------------
# Build features from the event stream
# ---------------------------------------------------------
state = build(event_frame)

glucose_events = event_frame[
    event_frame["kind"] == "glucose"
].copy()

glucose_minutes = glucose_events["timestamp"].map(minute)

duplicate_mask = glucose_minutes.duplicated(keep=False)
duplicate_glucose_rows = int(duplicate_mask.sum())

streamed = {}

for t in glucose_minutes.unique():
    t = int(t)

    if state.warm(t):
        streamed[t] = state.features_at(t)

if not streamed:
    raise SystemExit(
        "No warmed-up predictions could be generated. "
        "Check the event timestamps and glucose history."
    )

# ---------------------------------------------------------
# Compare against the training feature table
# ---------------------------------------------------------
grid["_minute"] = grid["timestamp"].map(minute)
matched_mask = grid["_minute"].isin(streamed.keys())
common = grid.loc[matched_mask].copy()

missing_rows = int((~matched_mask).sum())

print(
    f"Participant: {SUBJECT:03d}\n"
    f"Event order: {'shuffled' if SHUFFLE else 'in order'}\n"
    f"Training rows: {len(grid)}\n"
    f"Streamed timestamps: {len(streamed)}\n"
    f"Compared rows: {len(common)}\n"
    f"Training rows not reproduced: {missing_rows}\n"
    f"Duplicate glucose event rows: {duplicate_glucose_rows}"
)

if common.empty:
    raise SystemExit(
        "No timestamps matched. Check timezone and timestamp alignment."
    )

missing_features = [
    feature
    for feature in FEATURES
    if feature not in next(iter(streamed.values()))
]

if missing_features:
    raise SystemExit(
        "The feature engine did not generate required features:\n"
        + "\n".join(missing_features)
    )

rows = []

for feature in FEATURES:
    predictions = [
        streamed[int(t)][feature]
        for t in common["_minute"]
    ]

    if feature in CATEGORICAL:
        actual = common[feature].fillna("<NA>").astype(str).to_numpy()
        predicted = np.array(
            [
                "<NA>" if value is None or pd.isna(value) else str(value)
                for value in predictions
            ],
            dtype=object,
        )

        mismatches = int((predicted != actual).sum())
        max_diff = 0.0

    else:
        predicted = np.asarray(predictions, dtype=float)
        actual = pd.to_numeric(
            common[feature],
            errors="coerce",
        ).to_numpy(dtype=float)

        equal = np.isclose(
            predicted,
            actual,
            rtol=1e-4,
            atol=1e-3,
            equal_nan=True,
        )

        mismatches = int((~equal).sum())

        with np.errstate(invalid="ignore"):
            differences = np.abs(predicted - actual)

        finite_differences = differences[
            np.isfinite(differences)
        ]

        max_diff = (
            float(finite_differences.max())
            if len(finite_differences)
            else 0.0
        )

    rows.append(
        {
            "feature": feature,
            "mismatches": mismatches,
            "max_abs_diff": round(max_diff, 6),
        }
    )

results = pd.DataFrame(rows).sort_values(
    ["mismatches", "max_abs_diff"],
    ascending=[False, False],
)

bad = results[results["mismatches"] > 0]

print("\nFeature parity:")

if bad.empty:
    print("All compared feature values match.")
else:
    print(bad.to_string(index=False))

# ---------------------------------------------------------
# Test missing-glucose behavior
# ---------------------------------------------------------
glucose_events = glucose_events.reset_index(drop=True)

if len(glucose_events) < 10:
    raise SystemExit(
        "Not enough glucose readings for the missing-reading test."
    )

missing_ts = glucose_events["timestamp"].iloc[
    len(glucose_events) // 2
]
missing_minute = minute(missing_ts)

all_event_minutes = event_frame["timestamp"].map(minute)

remove_mask = (
    event_frame["kind"].eq("glucose")
    & all_event_minutes.eq(missing_minute)
)

without_reading = event_frame.loc[~remove_mask].copy()
state_missing = build(without_reading)

t = state_missing.minute(missing_ts)

checks = {
    "glucose_lag_15": t + 15,
    "glucose_lag_30": t + 30,
}

for feature, prediction_time in checks.items():
    value = state_missing.features_at(prediction_time)[feature]

    if not np.isnan(value):
        raise AssertionError(
            f"{feature} should be NaN after removing its source reading; "
            f"received {value!r}."
        )

if state_missing.warm(t + 15):
    raise AssertionError(
        "Warm-up should fail when a required glucose reading is missing."
    )

if state_missing.warm(t + 60):
    raise AssertionError(
        "Warm-up should fail while the missing reading remains in "
        "the required history window."
    )

print("\nMissing-reading test: OK")

# ---------------------------------------------------------
# Test timezone handling
# ---------------------------------------------------------
try:
    to_minute(pd.Timestamp("2020-05-01T10:00:00+00:00"))
except ValueError:
    pass
else:
    raise AssertionError(
        "Timezone-aware timestamps without a patient timezone "
        "should be rejected."
    )

aware_minute = to_minute(
    "2020-05-01T10:00:00+05:30",
    "Asia/Kolkata",
)
naive_minute = to_minute("2020-05-01T10:00:00")

if aware_minute != naive_minute:
    raise AssertionError(
        "Timezone conversion did not preserve the patient's local time."
    )

print("Timezone test: OK")

# ---------------------------------------------------------
# Final result
# ---------------------------------------------------------
parity_ok = (
    bad.empty
    and missing_rows == 0
    and duplicate_glucose_rows == 0
    and len(common) == len(grid)
)

print("\nPARITY", "OK" if parity_ok else "FAILED")

if not parity_ok:
    sys.exit(1)