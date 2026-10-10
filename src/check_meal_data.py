from pathlib import Path
import numpy as np
import pandas as pd

RAW = Path("data/raw/cgmacros")
pd.set_option("display.width", 200)

rows, meals_all = [], []

for folder in sorted(RAW.glob("CGMacros-*")):
    d = pd.read_csv(folder / f"{folder.name}.csv", low_memory=False)
    d.columns = d.columns.str.strip()
    d["Timestamp"] = pd.to_datetime(d["Timestamp"], errors="coerce")
    d = d.sort_values("Timestamp").reset_index(drop=True)

    # 1) Is Libre a 15-min signal interpolated to 1 min?
    g = d["Libre GL"].to_numpy()
    d2 = np.abs(np.diff(g, n=2))
    knots = np.where(d2 > 1e-6)[0] + 1         
    gaps = np.diff(knots)
    pct15 = round(100 * (gaps % 15 == 0).mean(), 1) if len(gaps) else None
    offset = int(np.bincount(knots % 15, minlength=15).argmax()) if len(knots) else None

    step = d["Timestamp"].diff().dt.total_seconds() / 60

    # 2) Meals
    m = d[d["Meal Type"].notna()].copy()
    m["subject"] = int(folder.name.split("-")[1])
    meals_all.append(m)
    days = (d["Timestamp"].max() - d["Timestamp"].min()).total_seconds() / 86400

    rows.append({
        "id": folder.name.split("-")[1],
        "days": round(days, 1),
        "knot_gaps_x15_%": pct15,
        "knot_offset": offset,
        "max_gap_min": step.max(),
        "meals": len(m),
        "meals_per_day": round(len(m) / days, 1),
        "photo_only_rows": int((d["Image path"].notna() & d["Meal Type"].isna()).sum()),
        "libre_min": round(d["Libre GL"].min()),
        "libre_max": round(d["Libre GL"].max()),
    })

print(pd.DataFrame(rows).to_string(index=False))

meals = pd.concat(meals_all, ignore_index=True)
print("\nMeal types:\n", meals["Meal Type"].value_counts().to_string())
print("\nMeal nutrients:\n", meals[["Calories", "Carbs", "Protein", "Fat", "Fiber", "Amount Consumed"]].describe().T.to_string())
print("\nAmount Consumed value counts (top 10):\n", meals["Amount Consumed"].value_counts().head(10).to_string())
print("\nMeal rows missing Carbs:", int(meals["Carbs"].isna().sum()))