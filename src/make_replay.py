import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/cgmacros")
OUT = Path("data/processed/replay")
OUT.mkdir(parents=True, exist_ok=True)
subjects = [int(a) for a in sys.argv[1:]] or [36, 20, 3]

CANON = {"timestamp": "Timestamp", "libregl": "Libre GL", "hr": "HR",
         "caloriesactivity": "Calories (Activity)", "mets": "METs", "intensity": "Intensity",
         "mealtype": "Meal Type", "calories": "Calories", "carbs": "Carbs", "protein": "Protein",
         "fat": "Fat", "fiber": "Fiber", "amountconsumed": "Amount Consumed"}
NUM = ["Libre GL", "HR", "Calories (Activity)", "METs", "Intensity", "Calories", "Carbs",
       "Protein", "Fat", "Fiber", "Amount Consumed"]
KIND_ORDER = {"wearable": 0, "meal": 1, "glucose": 2}


def meal_class(x):
    x = str(x).strip().lower()
    for name in ("breakfast", "lunch", "dinner"):
        if x.startswith(name[:5]):
            return name
    return "snack"


pq = pd.read_parquet("data/processed/glucose_15min.parquet", columns=["subject", "timestamp"])
meal_hours = []

for s in subjects:
    df = pd.read_csv(RAW / f"CGMacros-{s:03d}" / f"CGMacros-{s:03d}.csv", low_memory=False)
    df.columns = [CANON.get(re.sub(r"[^a-z0-9]", "", str(c).lower()), str(c).strip()) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    for c in CANON.values():
        if c not in df.columns:
            df[c] = np.nan
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = (df.dropna(subset=["Timestamp"]).sort_values("Timestamp")
            .drop_duplicates("Timestamp").reset_index(drop=True))
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    m = df["METs"].to_numpy(float) / 10.0
    derived = np.select([m <= 1.5, m <= 6.0], [0, 1], default=2).astype(float)
    derived[np.isnan(m)] = np.nan
    i = df["Intensity"].to_numpy(float)
    native = np.select([i <= 0, i <= 2], [0, 1], default=2).astype(float)
    native[np.isnan(i)] = np.nan
    df["act_level"] = np.where(np.isnan(derived), native, derived)

    grid = pq.loc[pq["subject"] == s, "timestamp"].sort_values()
    if grid.empty:
        print(f"participant {s}: not in the training table, skipped")
        continue
    t0 = grid.iloc[0]
    early = [t0 - pd.Timedelta(minutes=15 * k) for k in (4, 3, 2, 1)]
    is_grid = df["Timestamp"].isin(pd.DatetimeIndex(early + grid.tolist()))
    keep = df["Timestamp"] >= t0 - pd.Timedelta(minutes=60)
    d = df[keep].reset_index(drop=True)
    ig = is_grid[keep].reset_index(drop=True)
    has_meal = d["Meal Type"].notna() & ~(d["Amount Consumed"] == 0)

    wear = pd.DataFrame({"timestamp": d["Timestamp"], "kind": "wearable", "hr": d["HR"],
                         "act_level": d["act_level"], "activity_calories": d["Calories (Activity)"]})
    g = d[ig & d["Libre GL"].notna()]
    gl = pd.DataFrame({"timestamp": g["Timestamp"], "kind": "glucose", "value": g["Libre GL"]})
    me = d[has_meal]
    ml = pd.DataFrame({"timestamp": me["Timestamp"], "kind": "meal", "meal_type": me["Meal Type"],
                       "calories": me["Calories"], "carbs": me["Carbs"], "protein": me["Protein"],
                       "fat": me["Fat"], "fiber": me["Fiber"]})
    ev = pd.concat([wear, gl, ml], ignore_index=True)
    ev["_o"] = ev["kind"].map(KIND_ORDER)
    ev = ev.sort_values(["timestamp", "_o"], kind="stable").drop(columns="_o").reset_index(drop=True)
    path = OUT / f"events_{s:03d}.parquet"
    ev.to_parquet(path, index=False)

    meal_hours.append(pd.DataFrame({"type": me["Meal Type"].map(meal_class), "hour": me["Timestamp"].dt.hour}))
    print(f"participant {s:03d}: {len(wear):,} wearable samples | {len(gl)} glucose readings "
          f"(expected {len(grid) + 4}) | {len(ml)} meals | "
          f"{(d['Timestamp'].max() - d['Timestamp'].min()).days} days -> {path}")

if meal_hours:
    mh = pd.concat(meal_hours)
    print("\nmeal hour by type (are timestamps real local time-of-day?):")
    print(mh.groupby("type")["hour"].describe(percentiles=[0.1, 0.5, 0.9])[["count", "10%", "50%", "90%"]].round(1).to_string())