
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

OUT = Path("data/processed")
QUICK = "--quick" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
EVENT = args[0] if args else "high180"

meta = json.loads((OUT / "columns.json").read_text())
if EVENT not in meta["events"]:
    raise SystemExit(f"Unknown event {EVENT}. Use one of: {', '.join(meta['events'])}")
G, ALL_H = meta["groups"], meta["risk_horizons"]
THR, DIRECTION = meta["events"][EVENT]["threshold"], meta["events"][EVENT]["direction"]
H_ABL = [120] if QUICK else [60, 120, 240]
CURVE_H = [120] if QUICK else ALL_H

data = pd.read_parquet(OUT / "glucose_15min.parquet")
data["last_meal_type"] = pd.Categorical(
    data["last_meal_type"], categories=["none", "breakfast", "lunch", "dinner", "snack"])
d = data[data[f"{EVENT}_usable"] == 1].reset_index(drop=True)
FOLDS = sorted(d["fold"].unique())
fold_arr = d["fold"].to_numpy()
y_by_h = {h: d[f"{EVENT}_within_{h}"].to_numpy(dtype=float) for h in ALL_H}
glucose = d["glucose"].to_numpy(dtype=float)
no_model = glucose if DIRECTION == "above" else -glucose      # higher score = higher risk

print(f"event: {EVENT} ({DIRECTION} {THR}) | quick: {QUICK} | rows at risk: {len(d)} | "
      f"participants: {d['subject'].nunique()}")
print("prevalence by horizon:", {h: round(float(np.nanmean(y_by_h[h])), 3) for h in ALL_H})
print("events by fold at 120 min:", {int(f): int(np.nansum(y_by_h[120][fold_arr == f])) for f in FOLDS})


def cols(*names):
    return list(dict.fromkeys(c for n in names for c in G.get(n, [])))


STATIC_SMALL = [c for c in ("hba1c", "homa_ir") if c in G["static"]]
STATIC_DEMO = [c for c in ("age", "sex_male", "bmi") if c in G["static"]]
BASE = cols("glucose", "wearable", "meals", "time")
LADDER = {
    "1 CGM only": cols("glucose"),
    "2 CGM + EHR (all)": cols("glucose", "static"),
    "3 CGM + wearable": cols("glucose", "wearable"),
    "4 + logged meals": cols("glucose", "wearable", "meals"),
    "5 + time of day (no EHR)": BASE,
    "5b + consumed amounts": BASE + cols("meals_consumed"),
    "6a + HbA1c, HOMA-IR": BASE + STATIC_SMALL,
    "6b + age, sex, BMI": BASE + STATIC_DEMO,
    "6c + all EHR": BASE + cols("static"),
}
if QUICK:
    keep = ("1 CGM only", "5 + time of day (no EHR)", "6a + HbA1c, HOMA-IR")
    LADDER = {k: LADDER[k] for k in keep}
TREND = ["glucose", "glucose_change_15", "glucose_change_30"]


def make_model():
    return xgb.XGBClassifier(
        n_estimators=250, learning_rate=0.05, max_depth=4, min_child_weight=20,
        subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0, tree_method="hist",
        enable_categorical=True, eval_metric="logloss", n_jobs=-1, random_state=0)


def run_xgb(feats, horizons):
    """Out-of-fold predicted risk, one column per horizon (each fold trained on the others)."""
    X = d[feats]
    P = np.full((len(d), len(horizons)), np.nan)
    for j, h in enumerate(horizons):
        y = y_by_h[h]
        for f in FOLDS:
            tr, te = (fold_arr != f) & ~np.isnan(y), fold_arr == f
            if te.sum() == 0 or np.unique(y[tr]).size < 2:
                continue
            P[te, j] = make_model().fit(X.loc[tr], y[tr].astype(int)).predict_proba(X.loc[te])[:, 1]
    return P


def run_logit(feats, horizons):
    X = d[feats].to_numpy(float)
    P = np.full((len(d), len(horizons)), np.nan)
    for j, h in enumerate(horizons):
        y = y_by_h[h]
        for f in FOLDS:
            tr, te = (fold_arr != f) & ~np.isnan(y), fold_arr == f
            m = make_pipeline(SimpleImputer(), StandardScaler(), LogisticRegression(max_iter=500))
            P[te, j] = m.fit(X[tr], y[tr].astype(int)).predict_proba(X[te])[:, 1]
    return P


def score(y, p, brier=True):
    ok = ~np.isnan(y) & ~np.isnan(p)
    y, p, fo = y[ok], p[ok], fold_arr[ok]
    if np.unique(y).size < 2:
        return {"auroc": np.nan, "auroc_fold_sd": np.nan, "ap": np.nan, "prevalence": np.nan, "bss": np.nan}
    per = [roc_auc_score(y[fo == f], p[fo == f]) for f in np.unique(fo) if np.unique(y[fo == f]).size == 2]
    out = {"auroc": roc_auc_score(y, p), "auroc_fold_sd": float(np.std(per)) if per else np.nan,
           "ap": average_precision_score(y, p), "prevalence": float(y.mean()), "bss": np.nan}
    if brier:
        out["bss"] = 1 - brier_score_loss(y, p) / (y.mean() * (1 - y.mean()))
    return out


# ------------------------------------------------------------------ ablation
rows = []
for h in H_ABL:
    rows.append({"model": "0 current glucose (no model)", "h": h, **score(y_by_h[h], no_model, brier=False)})
P = run_logit(TREND, H_ABL)
for j, h in enumerate(H_ABL):
    rows.append({"model": "0b glucose + trend (logistic)", "h": h, **score(y_by_h[h], P[:, j])})
for name, feats in LADDER.items():
    t0 = time.time()
    P = run_xgb(feats, H_ABL)
    for j, h in enumerate(H_ABL):
        rows.append({"model": name, "h": h, **score(y_by_h[h], P[:, j])})
    print(f"  done: {name} ({len(feats)} features, {time.time() - t0:.0f}s)")
res = pd.DataFrame(rows)

print(f"\n=== AUROC (pooled out-of-fold, +/- SD across folds) for {EVENT} ===")
cell = res.assign(c=res["auroc"].round(3).astype(str) + " +/- " + res["auroc_fold_sd"].round(3).astype(str))
print(cell.pivot(index="model", columns="h", values="c").to_string())
print("\n=== AVERAGE PRECISION (random = prevalence) ===")
print(res.pivot(index="model", columns="h", values="ap").round(3).to_string())
print("\n=== BRIER SKILL SCORE (0 = prevalence baseline; higher is better) ===")
print(res.pivot(index="model", columns="h", values="bss").round(3).to_string())

# ------------------------------------------------------------------ risk curve (no-EHR vs all-EHR)
VARIANTS = {"noehr": ("no EHR", BASE), "ehr": ("with all EHR", BASE + cols("static"))}
oof = d[["subject", "timestamp", "fold", "glucose", f"{EVENT}_tte", f"{EVENT}_event"]
        + [f"{EVENT}_within_{h}" for h in ALL_H]].copy()
curve = []
for short, (vname, feats) in VARIANTS.items():
    t0 = time.time()
    P = np.maximum.accumulate(run_xgb(feats, CURVE_H), axis=1)      # risk cannot shrink with the horizon
    for j, h in enumerate(CURVE_H):
        oof[f"p_{short}_{h}"] = P[:, j]
        m = score(y_by_h[h], P[:, j])
        curve.append({"variant": vname, "h": h, **{k: round(v, 3) for k, v in m.items()}})
    print(f"  done risk curve: {vname} ({time.time() - t0:.0f}s)")
print(f"\n=== RISK CURVE: {EVENT}, all horizons ===")
print(pd.DataFrame(curve).to_string(index=False))

# ------------------------------------------------------------------ non-trivial cases only
far = (glucose < THR - 30) if DIRECTION == "above" else (glucose > THR + 30)
rows = []
for h in CURVE_H:
    y, p = y_by_h[h], oof[f"p_noehr_{h}"].to_numpy()
    m = far & ~np.isnan(y) & ~np.isnan(p)
    if m.sum() and 0 < y[m].sum() < m.sum():
        rows.append({"h": h, "rows": int(m.sum()), "events": int(y[m].sum()),
                     "auroc": round(roc_auc_score(y[m], p[m]), 3)})
print("\n=== AUROC (no-EHR model) when glucose is >= 30 mg/dL from the threshold ===")
print(pd.DataFrame(rows).to_string(index=False))

# ------------------------------------------------------------------ calibration
y, p = y_by_h[120], oof["p_noehr_120"].to_numpy()
ok = ~np.isnan(y) & ~np.isnan(p)
bins = pd.qcut(p[ok], 5, duplicates="drop")
cal = (pd.DataFrame({"predicted": p[ok], "observed": y[ok]}).groupby(bins, observed=True)
       .agg(predicted=("predicted", "mean"), observed=("observed", "mean"), n=("observed", "size")).round(3))
print("\n=== CALIBRATION at 120 min (no-EHR model) ===")
print(cal.to_string())

if not QUICK:
    path = OUT / f"oof_{EVENT}.parquet"
    oof.to_parquet(path, index=False)
    print("\nSaved:", path)
else:
    print("\nQuick test complete. No OOF file written.")