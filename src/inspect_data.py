
from pathlib import Path
import pandas as pd

RAW = Path("data/raw/cgmacros")

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

folders = sorted(RAW.glob("CGMacros-*"))
print("Participant folders:", len(folders))
print("IDs:", [f.name.split("-")[1] for f in folders])

bio_path = RAW / "bio.csv"

if bio_path.exists():
    bio = pd.read_csv(bio_path)
    print("\n=== bio.csv ===", bio.shape)
    print("Columns:", bio.columns.tolist())
    print(bio.describe(include="all").T.to_string())

p = RAW / "CGMacros-001" / "CGMacros-001.csv"

if p.exists():
    ts = pd.read_csv(p, low_memory=False)
    print("\n=== CGMacros-001 ===", ts.shape)
    print("\nData types:\n", ts.dtypes.to_string())
    print("\nFirst rows:\n", ts.head(3).to_string())

    ts["Timestamp"] = pd.to_datetime(ts["Timestamp"], errors="coerce")
    valid_times = ts["Timestamp"].dropna().sort_values()
    print("\nInvalid timestamps:", ts["Timestamp"].isna().sum())
    print("Start:", valid_times.min(), "| End:", valid_times.max())
    print(
        "Median step (min):",
        valid_times.diff().dt.total_seconds().median() / 60
    )

    print("\nColumns:", ts.columns.tolist())

    excluded = {
        "Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL",
        "HR", "Calories (Activity)", "METs"
    }
    meal_cols = [c for c in ts.columns if c not in excluded]
    print("Potential meal/context columns:", meal_cols)

    if meal_cols:
        meals = ts[ts[meal_cols].notna().any(axis=1)]
        print("Rows with meal/context data:", len(meals))
        print(meals.head(5).to_string(index=False))

rows = []

for folder in folders:
    file = folder / f"{folder.name}.csv"

    if not file.exists():
        print("Missing participant file:", file)
        continue

    d = pd.read_csv(file, low_memory=False)

    rows.append({
        "id": folder.name.split("-")[1],
        "rows": len(d),
        "libre_%": round(100 * d["Libre GL"].notna().mean(), 1)
        if "Libre GL" in d else None,
        "dexcom_%": round(100 * d["Dexcom GL"].notna().mean(), 1)
        if "Dexcom GL" in d else None,
        "hr_%": round(100 * d["HR"].notna().mean(), 1)
        if "HR" in d else None,
    })

print("\n=== Coverage per participant ===")
print(pd.DataFrame(rows).to_string(index=False))
