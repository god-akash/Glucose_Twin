import argparse
import time

import pandas as pd
import requests


MACROS = ["calories", "carbs", "protein", "fat", "fiber"]
ap = argparse.ArgumentParser()
ap.add_argument("subject", type=int)
ap.add_argument("--speed", type=int, default=15, help="patient minutes per second")
ap.add_argument("--ff-hours", type=float, default=0, help="hours loaded instantly before the live replay")
ap.add_argument("--api", default="http://127.0.0.1:8000")
ap.add_argument("--mode", default="cv", choices=["cv", "final"])
ap.add_argument("--patient-id", default=None)
a = ap.parse_args()

pid = a.patient_id or f"cgm-{a.subject:03d}"
ev = pd.read_parquet(f"data/processed/replay/events_{a.subject:03d}.parquet")
stamps = ev["timestamp"]


def post(path, payload):
    r = requests.post(a.api + path, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def build(chunk):
    w, g, m = [], [], []
    for r in chunk.itertuples(index=False):
        ts = r.timestamp.isoformat()
        if r.kind == "wearable":
            d = {"timestamp": ts}
            for k in ("hr", "act_level", "activity_calories"):
                if pd.notna(getattr(r, k)):
                    d[k] = float(getattr(r, k))
            w.append(d)
        elif r.kind == "glucose":
            g.append({"timestamp": ts, "value": float(r.value)})
        else:
            m.append({"timestamp": ts, "meal_type": str(r.meal_type),
                      **{k: float(getattr(r, k)) for k in MACROS if pd.notna(getattr(r, k))}})
    return w, g, m



cursor = stamps.iloc[0]
end = stamps.iloc[-1]
ff_end = cursor + pd.Timedelta(hours=a.ff_hours)

STATIC = ["age", "sex_male", "bmi", "hba1c", "fasting_glucose", "insulin", "homa_ir"]
prof = pd.read_parquet("data/processed/glucose_15min.parquet", columns=["subject"] + STATIC)
prof = prof[prof["subject"] == a.subject].head(1)
profile = {k: float(prof.iloc[0][k]) for k in STATIC} if len(prof) else None
print(post("/reset", {"patient_id": pid, "mode": a.mode, "subject": a.subject, "profile": profile}))

while cursor <= end:
    fast = cursor < ff_end
    nxt = cursor + pd.Timedelta(minutes=1440 if fast else a.speed)
    lo, hi = stamps.searchsorted(cursor, side="left"), stamps.searchsorted(nxt, side="left")
    cursor = nxt
    if hi <= lo:
        continue
    w, g, m = build(ev.iloc[lo:hi])
    resp = post("/ingest", {"patient_id": pid, "wearable": w, "glucose": g, "meals": m, "do_predict": not fast})
    if fast:
        continue
    late = resp["latest"]
    if resp["new_readings"] and late and late["predicted"]:
        t = late["tasks"].get("high180", {})
        risk = t.get("risk", {}).get("120")
        print(f"{late['timestamp']}  glucose {late['glucose']:.0f}  "
              + (f"high180 risk (2 h) {risk:.2f} [{t['level']}]" if risk is not None else f"high180: {t.get('status')}"))
    time.sleep(1)
print("replay finished") 