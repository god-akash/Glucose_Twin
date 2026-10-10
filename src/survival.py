import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

warnings.filterwarnings("ignore")

OUT = Path("data/processed")
STEP = 15
QUICK = "--quick" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
EVENT = args[0] if args else "high180"
STATIC = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--static=")), "none")
if STATIC not in {"none", "small", "full"}:
    raise SystemExit("--static must be none, small, or full")

meta = json.loads((OUT / "columns.json").read_text())
if EVENT not in meta["events"]:
    raise SystemExit(f"Unknown event: {EVENT}. Use one of: {', '.join(meta['events'])}")
G = meta["groups"]
RISK_H = meta["risk_horizons"]
K = len(meta["future_horizons"])
MAX_MIN = K * STEP
EVAL_H = [60, 120] if QUICK else [30, 60, 120, 240, 360]

features = G["glucose"] + G["wearable"] + G["meals"] + G["time"]
if STATIC == "small":
    features += [c for c in ("hba1c", "homa_ir") if c in G["static"]]
elif STATIC == "full":
    features += G["static"]
features = list(dict.fromkeys(features))

data = pd.read_parquet(OUT / "glucose_15min.parquet")
data["last_meal_type"] = pd.Categorical(
    data["last_meal_type"], categories=["none", "breakfast", "lunch", "dinner", "snack"])
d = data[data[f"{EVENT}_usable"] == 1].reset_index(drop=True)

Xd = d[features].copy()
num_cols = [c for c in features if c != "last_meal_type"]
Xd[num_cols] = Xd[num_cols].astype("float32")

has_event = d[f"{EVENT}_event"].to_numpy().astype(bool)
follow_steps = np.floor(d[f"{EVENT}_follow"].to_numpy(float) / STEP).astype(int)
tte = d[f"{EVENT}_tte"].to_numpy(float)
event_step = np.where(has_event & ~np.isnan(tte), np.floor(tte / STEP), 0).astype(int)
fold = d["fold"].to_numpy()
FOLDS = sorted(np.unique(fold))
y_h = {h: d[f"{EVENT}_within_{h}"].to_numpy(float) for h in RISK_H}

print(f"event: {EVENT} | static: {STATIC} | quick: {QUICK} | rows at risk: {len(d)} | "
      f"participants: {d['subject'].nunique()} | features: {len(features)} | events: {int(has_event.sum())}")


def expand(idx):
    L = np.where(has_event[idx], np.minimum(event_step[idx], follow_steps[idx]), follow_steps[idx])
    L = np.maximum(L, 0)
    rows = np.repeat(idx, L)
    k = np.arange(L.sum()) - np.repeat(np.cumsum(L) - L, L) + 1
    X = Xd.iloc[rows].reset_index(drop=True)
    X["k_min"] = (k * STEP).astype("float32")
    y = (has_event[rows] & (k == event_step[rows])).astype(int)
    return X, y


def fit_hazard(train_idx):
    X, y = expand(train_idx)
    print(f"    person-period rows: {len(X):,} | event steps: {int(y.sum())}")
    model = xgb.XGBClassifier(
        n_estimators=120 if QUICK else 300, learning_rate=0.06, max_depth=5,
        min_child_weight=50, subsample=0.7, colsample_bytree=0.8, reg_lambda=10.0,
        tree_method="hist", enable_categorical=True, eval_metric="logloss",
        n_jobs=-1, random_state=0)
    return model.fit(X, y)


def predict_curve(model, idx):
    n = len(idx)
    X = Xd.iloc[np.repeat(idx, K)].reset_index(drop=True)
    X["k_min"] = np.tile(np.arange(1, K + 1) * STEP, n).astype("float32")
    hazard = np.clip(model.predict_proba(X)[:, 1].reshape(n, K), 0.0, 1.0)
    survival = np.cumprod(1.0 - hazard, axis=1)
    return hazard, survival, 1.0 - survival


risk_all = np.full((len(d), K), np.nan)
expected_tte = np.full(len(d), np.nan)
median_tte = np.full(len(d), np.nan)
const_tte = np.full(len(d), np.nan)
steps_min = np.arange(1, K + 1) * STEP

for f in FOLDS:
    t0 = time.time()
    train_idx = np.flatnonzero(fold != f)
    test_idx = np.flatnonzero(fold == f)
    print(f"\nfold {f}: train anchors={len(train_idx):,} | test anchors={len(test_idx):,}")
    if QUICK:
        train_idx = train_idx[::3]

    model = fit_hazard(train_idx)
    train_events = train_idx[has_event[train_idx] & ~np.isnan(tte[train_idx])]
    const_tte[test_idx] = np.median(tte[train_events])

    hazard, survival, cumulative = predict_curve(model, test_idx)
    risk_all[test_idx] = cumulative

    density = np.hstack([np.ones((len(test_idx), 1)), survival[:, :-1]]) * hazard
    expected_tte[test_idx] = (density * steps_min).sum(1) / np.maximum(density.sum(1), 1e-9)
    reached = cumulative >= 0.5
    median_tte[test_idx] = np.where(reached.any(1), (reached.argmax(1) + 1) * STEP, np.nan)
    print(f"fold {f} done in {time.time() - t0:.0f}s")

valid = risk_all[~np.isnan(risk_all).all(axis=1)]
assert (np.diff(valid, axis=1) >= -1e-9).all(), "cumulative risk decreased"


def score(y, p):
    ok = ~np.isnan(y) & ~np.isnan(p)
    y, p, fo = y[ok], p[ok], fold[ok]
    if len(y) == 0 or np.unique(y).size < 2:
        return {"auroc": np.nan, "auroc_fold_sd": np.nan, "ap": np.nan, "bss": np.nan}
    per = [roc_auc_score(y[fo == f], p[fo == f]) for f in np.unique(fo)
           if np.unique(y[fo == f]).size == 2]
    prev = y.mean()
    return {"auroc": roc_auc_score(y, p),
            "auroc_fold_sd": float(np.std(per)) if per else np.nan,
            "ap": average_precision_score(y, p),
            "bss": 1 - brier_score_loss(y, p) / (prev * (1 - prev))}


def direct_classifiers(horizons):
    P = np.full((len(d), len(horizons)), np.nan)
    for j, h in enumerate(horizons):
        y = y_h[h]
        for f in FOLDS:
            tr, te = (fold != f) & ~np.isnan(y), fold == f
            m = xgb.XGBClassifier(
                n_estimators=250, learning_rate=0.05, max_depth=4, min_child_weight=20,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0, tree_method="hist",
                enable_categorical=True, eval_metric="logloss", n_jobs=-1, random_state=0)
            P[te, j] = m.fit(Xd.loc[tr], y[tr].astype(int)).predict_proba(Xd.loc[te])[:, 1]
    return P


Pd = direct_classifiers(EVAL_H)
rows = []
for j, h in enumerate(EVAL_H):
    ix = h // STEP - 1
    for name, p in (("hazard model", risk_all[:, ix]), ("direct classifier", Pd[:, j])):
        rows.append({"method": name, "h": h,
                     **{k: round(float(v), 3) for k, v in score(y_h[h], p).items()}})
cmp_df = pd.DataFrame(rows)

for metric, title in (("auroc", "AUROC"), ("auroc_fold_sd", "AUROC FOLD SD"),
                      ("ap", "AVERAGE PRECISION"), ("bss", "BRIER SKILL SCORE")):
    print(f"\n=== {title}: hazard model vs direct classifiers ({EVENT}, static={STATIC}) ===")
    print(cmp_df.pivot(index="method", columns="h", values=metric).to_string())

y120, p120 = y_h[120], risk_all[:, 120 // STEP - 1]
ok = ~np.isnan(y120) & ~np.isnan(p120)
if ok.sum():
    bins = pd.qcut(p120[ok], 5, duplicates="drop")
    cal = (pd.DataFrame({"predicted": p120[ok], "observed": y120[ok]})
           .groupby(bins, observed=True)
           .agg(predicted=("predicted", "mean"), observed=("observed", "mean"),
                n=("observed", "size")).round(3))
    print("\n=== CALIBRATION at 120 min (hazard model) ===")
    print(cal.to_string())

timing = []
for label, limit in (("event within 120 min", 120), (f"event within {MAX_MIN} min", MAX_MIN)):
    m = has_event & ~np.isnan(tte) & (tte <= limit) & ~np.isnan(expected_tte)
    if m.sum() == 0:
        continue
    timing.append({
        "subset": label, "n": int(m.sum()),
        "MAE_model_min": round(float(np.abs(expected_tte[m] - tte[m]).mean()), 1),
        "MAE_constant_min": round(float(np.abs(const_tte[m] - tte[m]).mean()), 1),
        "spearman": round(float(pd.Series(expected_tte[m]).rank().corr(pd.Series(tte[m]).rank())), 3)})
print("\n=== TIMING SKILL (constant = median event time in training folds) ===")
print(pd.DataFrame(timing).to_string(index=False))

if not QUICK:
    out = pd.DataFrame({"subject": d["subject"], "timestamp": d["timestamp"], "fold": fold,
                        "glucose": d["glucose"], "tte": tte, "event": has_event.astype(int),
                        "expected_tte": expected_tte, "median_tte": median_tte})
    for i in range(K):
        out[f"risk_{(i + 1) * STEP}"] = risk_all[:, i]
    path = OUT / f"oof_surv_{EVENT}_{STATIC}.parquet"
    out.to_parquet(path, index=False)
    print(f"\nSaved: {path}")
else:
    print("\nQuick test complete. No OOF file written.")