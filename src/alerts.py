import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data/processed")
EVENT = sys.argv[1] if len(sys.argv) > 1 else "high180"
H = 120
THRESHOLDS = [0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
OFFSETS = [5,10, 20, 30]


meta = json.loads((OUT / "columns.json").read_text())
thr_g = meta["events"][EVENT]["threshold"]
above = meta["events"][EVENT]["direction"] == "above"

d = (pd.read_parquet(OUT / f"oof_{EVENT}.parquet")
       .sort_values(["subject", "timestamp"]).reset_index(drop=True))
subj = d["subject"].to_numpy()
ts = d["timestamp"]
risk = d[f"p_noehr_{H}"].to_numpy()
glucose = d["glucose"].to_numpy()
y = d[f"{EVENT}_within_{H}"].to_numpy()
days = len(d) * 15 / 1440

gap = ts.diff().dt.total_seconds().div(60).to_numpy()
same = np.r_[False, subj[1:] == subj[:-1]] & (gap <= 30)

ev = d[d[f"{EVENT}_event"] == 1]
cross = ev["timestamp"] + pd.to_timedelta(ev[f"{EVENT}_tte"], unit="m")
cr = pd.DataFrame({"subject": ev["subject"].to_numpy(), "cross": cross.to_numpy()}).drop_duplicates()
n_cross = len(cr)
ts_np = ts.to_numpy()


def evaluate(alert, label):
    start = alert & ~(np.r_[False, alert[:-1]] & same)
    yy = y[start]
    yy = yy[~np.isnan(yy)]
    a_ts, a_sub = ts_np[alert], subj[alert]
    lead = []
    for s, g in cr.groupby("subject"):
        at = a_ts[a_sub == s]
        if len(at) == 0:
            continue
        c = g["cross"].to_numpy()
        lo = np.searchsorted(at, c - np.timedelta64(H, "m"), side="left")
        hi = np.searchsorted(at, c, side="left")
        ok = hi > lo
        if ok.any():
            lead.extend(((c[ok] - at[lo[ok]]) / np.timedelta64(1, "m")).tolist())
    return {"method": label,
            "alerts_per_day": round(start.sum() / days, 2),
            "precision_%": round(100 * yy.mean(), 1) if len(yy) else np.nan,
            "crossings_caught_%": round(100 * len(lead) / n_cross, 1),
            "median_lead_min": round(float(np.median(lead)), 0) if lead else np.nan}


rows = [evaluate(risk >= t, f"twin: risk within {H} min >= {t:.2f}") for t in THRESHOLDS]
for off in OFFSETS:
    g = thr_g - off if above else thr_g + off
    rows.append(evaluate(glucose >= g if above else glucose <= g,
                         f"rule: glucose {'>=' if above else '<='} {g}"))

print(f"{EVENT}: {n_cross} threshold crossings, {days:.0f} person-days of at-risk monitoring")
print("precision = alerts followed by a crossing within 2 h; lead = alert time to crossing, max 120 min")
print(pd.DataFrame(rows).to_string(index=False))