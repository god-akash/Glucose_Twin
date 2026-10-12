import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from server.features import PatientState, from_minute

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "models" / "meta.json").read_text())
COLS = json.loads((ROOT / "data" / "processed" / "columns.json").read_text())
FEATURES = MANIFEST["features"]
MEAL_TYPES = MANIFEST["meal_types"]
HORIZONS = MANIFEST["horizons"]
THRESHOLDS = MANIFEST["thresholds"]
FOLD_OF = MANIFEST["fold_of_subject"]
EVENTS = {k: (v["threshold"], v["direction"]) for k, v in MANIFEST["events"].items()}
CAPS = COLS["macro_caps"]
CATEGORIES = {"last_meal_type": MEAL_TYPES}

TASKS = {}
for _ev, (_thr, _dir) in EVENTS.items():
    TASKS[_ev] = {"kind": "glucose_event", "features": FEATURES, "horizons": HORIZONS,
                  "threshold": _thr, "direction": _dir, "alerts": THRESHOLDS[_ev],
                  "exploratory": _ev == "low70"}
_registry = ROOT / "models" / "registry.json"
if _registry.exists():
    TASKS.update(json.loads(_registry.read_text()))

LOCK = threading.Lock()
PATIENTS = {}
MODEL_CACHE = {}


def load_models(folder):
    if folder not in MODEL_CACHE:
        loaded = {}
        for task, spec in TASKS.items():
            for h in spec["horizons"]:
                path = ROOT / "models" / folder / f"{task}_{h}.json"
                if path.exists():
                    m = xgb.XGBClassifier(enable_categorical=True)
                    m.load_model(str(path))
                    loaded[(task, h)] = m
        MODEL_CACHE[folder] = loaded
    return MODEL_CACHE[folder]


def frame(feats, names):
    X = pd.DataFrame([{k: feats[k] for k in names}])
    for c in names:
        if c in CATEGORIES:
            X[c] = pd.Categorical(X[c], categories=CATEGORIES[c])
        else:
            X[c] = X[c].astype("float32")
    return X


def predict(folder, feats, glucose):
    models = load_models(folder)
    out = {}
    for task, spec in TASKS.items():
        missing = [f for f in spec["features"] if f not in feats]
        if missing:
            out[task] = {"status": "missing_inputs", "missing": missing}
            continue
        hs = spec["horizons"]
        if any((task, h) not in models for h in hs):
            out[task] = {"status": "model_unavailable"}
            continue
        base = {"kind": spec.get("kind"), "threshold": spec.get("threshold"),
                "direction": spec.get("direction"), "exploratory": spec.get("exploratory", False)}
        if spec.get("kind") == "glucose_event":
            thr, direction = spec["threshold"], spec["direction"]
            if (glucose > thr) if direction == "above" else (glucose < thr):
                out[task] = {**base, "status": "in_event"}
                continue
        X = frame(feats, spec["features"])
        p = np.maximum.accumulate([float(models[(task, h)].predict_proba(X)[0, 1]) for h in hs])
        first50 = next((h for h, v in zip(hs, p) if v >= 0.5), None)
        ref = p[hs.index(120)] if 120 in hs else p[-1]
        a = spec["alerts"]
        level = "alert" if ref >= a["balanced"] else "watch" if ref >= a["sensitive"] else "ok"
        out[task] = {**base, "status": "ok", "level": level, "risk_50_by_min": first50,
                     "risk": {str(h): round(float(v), 4) for h, v in zip(hs, p)}}
    return out


class Patient:
    def __init__(self, pid, folder, subject=None, tz=None, profile=None):
        self.pid, self.folder, self.subject, self.tz = pid, folder, subject, tz
        self.profile = profile or {}
        self.state = PatientState(CAPS, EVENTS, tz=tz)
        self.history = []

    def feats(self, t, extra=None):
        return {**self.state.features_at(t, extra=extra), **self.profile}

    def on_reading(self, t, do_predict):
        g = self.state.glucose_at(t)
        warming = not self.state.warm(t)
        entry = {"timestamp": from_minute(t).isoformat(), "t": t, "glucose": round(g, 1),
                 "warming_up": warming, "predicted": False, "tasks": {}}
        if do_predict and not warming:
            entry["tasks"] = predict(self.folder, self.feats(t), g)
            entry["predicted"] = True
        self.history.append(entry)
        return entry


class MealIn(BaseModel):
    meal_type: str = "snack"
    calories: Optional[float] = None
    carbs: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    fiber: Optional[float] = None


class MealEvent(MealIn):
    timestamp: datetime


class WearableIn(BaseModel):
    timestamp: datetime
    hr: Optional[float] = None
    act_level: Optional[float] = None
    activity_calories: Optional[float] = None


class GlucoseIn(BaseModel):
    timestamp: datetime
    value: float


class IngestIn(BaseModel):
    patient_id: str
    wearable: List[WearableIn] = []
    glucose: List[GlucoseIn] = []
    meals: List[MealEvent] = []
    do_predict: bool = True


class ResetIn(BaseModel):
    patient_id: str
    mode: str = "final"
    subject: Optional[int] = None
    timezone: Optional[str] = None
    profile: Optional[Dict[str, float]] = None


class WhatIfIn(BaseModel):
    patient_id: str
    meal: MealIn


def meal_dict(m):
    return {"meal_type": m.meal_type, "calories": m.calories, "carbs": m.carbs,
            "protein": m.protein, "fat": m.fat, "fiber": m.fiber}


def get_patient(pid):
    p = PATIENTS.get(pid)
    if p is None:
        raise HTTPException(404, f"unknown patient {pid}; call /reset or /ingest first")
    return p


# api 

app = FastAPI(title="Glucose Twin API")


@app.get("/health")
def health():
    return {"status": "ok", "patients": len(PATIENTS)}


@app.get("/config")
def config():
    return {"horizons": HORIZONS,
            "tasks": {k: {kk: vv for kk, vv in v.items() if kk != "features"} | {"n_features": len(v["features"])}
                      for k, v in TASKS.items()}}


@app.post("/reset")
def reset(req: ResetIn):
    folder = "final"
    if req.mode == "cv":
        if req.subject is None or str(req.subject) not in FOLD_OF:
            raise HTTPException(400, "mode 'cv' needs a subject id from the training data")
        folder = f"fold{FOLD_OF[str(req.subject)]}"
    elif req.mode != "final":
        raise HTTPException(400, "mode must be 'final' or 'cv'")
    if not (ROOT / "models" / folder).exists():
        raise HTTPException(500, f"model folder {folder} not found")
    if req.timezone:
        try:
            pd.Timestamp("2020-01-01").tz_localize(req.timezone)
        except Exception:
            raise HTTPException(422, f"unknown timezone {req.timezone}")
    with LOCK:
        PATIENTS[req.patient_id] = Patient(req.patient_id, folder, req.subject, req.timezone, req.profile)
    return {"patient_id": req.patient_id, "model_folder": folder, "timezone": req.timezone}


@app.post("/ingest")
def ingest(req: IngestIn):
    with LOCK:
        p = PATIENTS.get(req.patient_id)
        if p is None:
            p = PATIENTS[req.patient_id] = Patient(req.patient_id, "final")
        try:
            for x in (*req.wearable, *req.glucose, *req.meals):
                p.state.minute(x.timestamp)
        except ValueError as e:
            raise HTTPException(422, str(e))
        for w in req.wearable:
            p.state.add_wearable(w.timestamp, w.hr, w.act_level, w.activity_calories)
        for m in req.meals:
            p.state.add_meal(m.timestamp, meal_dict(m))
        times = sorted({p.state.add_glucose(g.timestamp, g.value) for g in req.glucose})
        last_t = p.history[-1]["t"] if p.history else -10 ** 12
        made = late = 0
        for t in times:
            if t <= last_t:
                late += 1
                continue
            p.on_reading(t, req.do_predict)
            made += 1
        return {"patient_id": p.pid, "wearable": len(req.wearable), "glucose": len(req.glucose),
                "meals": len(req.meals), "new_readings": made, "late_readings": late,
                "latest": p.history[-1] if p.history else None}


@app.get("/patients")
def patients():
    return [{"patient_id": p.pid, "model_folder": p.folder, "subject": p.subject, "timezone": p.tz,
             "readings": len(p.history), "last": p.history[-1]["timestamp"] if p.history else None}
            for p in PATIENTS.values()]


@app.get("/patients/{pid}/latest")
def latest(pid: str):
    with LOCK:
        p = get_patient(pid)
        if not p.history:
            raise HTTPException(404, "no glucose readings yet")
        return {"model_folder": p.folder, "profile": p.profile,**p.history[-1]}
            # return {"model_folder": p.folder,  **p.history[-1]}


@app.get("/patients/{pid}/history")
def history(pid: str, limit: int = 400):
    with LOCK:
        return get_patient(pid).history[-limit:]


@app.post("/whatif")
def whatif(req: WhatIfIn):
    with LOCK:
        p = get_patient(req.patient_id)
        if not p.history or p.history[-1]["warming_up"]:
            raise HTTPException(409, "patient needs at least one hour of glucose history")
        last = p.history[-1]
        t = last["t"]
        g = p.state.glucose_at(t)
        extra = p.state.prepare_meal(t, meal_dict(req.meal))
        sim = predict(p.folder, p.feats(t, extra=extra), g)
        base = last["tasks"] if last["predicted"] else predict(p.folder, p.feats(t), g)
    return {"timestamp": last["timestamp"], "glucose": last["glucose"], "baseline": base, "with_meal": sim,
            "note": "Model estimate of how risk changes if this meal is logged now. "
                    "It reflects patterns in the training data, not a causal or clinical prediction."}

@app.get("/metrics")
def metrics():
    path = ROOT / "data" / "processed" / "train_oof_metrics.csv"
    if not path.exists():
        raise HTTPException(404, "train_oof_metrics.csv not found; run train_model.py")
    return json.loads(pd.read_csv(path).to_json(orient="records"))