import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from server.features import PatientState, from_minute

from server.explain import ( # type: ignore
    LABELS,
    build_facts,
    explain as explain_text,
)
from dotenv import load_dotenv
load_dotenv()

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
    TASKS[_ev] = {
        "kind": "glucose_event",
        "features": FEATURES,
        "horizons": HORIZONS,
        "threshold": _thr,
        "direction": _dir,
        "alerts": THRESHOLDS[_ev],
        "exploratory": _ev == "low70",
    }
_registry = ROOT / "models" / "registry.json"
if _registry.exists():
    TASKS.update(json.loads(_registry.read_text()))

LOCK = threading.Lock()
PATIENTS = {}
MODEL_CACHE = {}
TIMING_DIR = ROOT / "models" / "timing"
TIMING_EVENTS = {"high180", "high140"}
TIMING_CACHE = {}
ALERT_RECOVERY_MARGIN = 0.05


def choose_alert_level(probability, alerts, previous_level=None):
    sensitive = float(alerts["sensitive"])
    balanced = float(alerts["balanced"])
    margin = ALERT_RECOVERY_MARGIN

    # Escalate immediately when the alert threshold is reached.
    if probability >= balanced:
        return "alert"

    # An existing alert is retained until risk falls sufficiently.
    if previous_level == "alert":
        if probability >= max(0.0, balanced - margin):
            return "alert"

        if probability >= max(0.0, sensitive - margin):
            return "watch"

        return "ok"

    # An existing watch state has a separate recovery threshold.
    if previous_level == "watch":
        if probability >= max(0.0, sensitive - margin):
            return "watch"

        return "ok"

    # Normal entry rules for a new or cleared state.
    if probability >= sensitive:
        return "watch"

    return "ok"

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


def reach_minutes(hs, p, level):
    if p[0] >= level:
        return hs[0]
    for i in range(1, len(hs)):
        if p[i] >= level:
            frac = (level - p[i - 1]) / (p[i] - p[i - 1])
            return int(round((hs[i - 1] + frac * (hs[i] - hs[i - 1])) / 5) * 5)
    return None


def predict(folder, feats, glucose, previous_levels=None):
    models = load_models(folder)
    out = {}

    for task, spec in TASKS.items():
        missing = [f for f in spec["features"] if f not in feats]

        if missing:
            out[task] = {
                "status": "missing_inputs",
                "missing": missing,
            }
            continue

        hs = spec["horizons"]

        if any((task, h) not in models for h in hs):
            out[task] = {
                "status": "model_unavailable",
            }
            continue

        base = {
            "kind": spec.get("kind"),
            "threshold": spec.get("threshold"),
            "direction": spec.get("direction"),
            "exploratory": spec.get("exploratory", False),
        }

        # Do not estimate time to a threshold that has already
        # been crossed at the current reading.
        if spec.get("kind") == "glucose_event":
            threshold = spec["threshold"]
            direction = spec["direction"]

            already_in_event = (
                glucose > threshold if direction == "above" else glucose < threshold
            )

            if already_in_event:
               out[task] = {
        **base,
        "status": "in_event",
        "level": "alert",
    }
            continue

        X = frame(feats, spec["features"])

        # Existing classifier risk predictions remain unchanged.
        p = np.maximum.accumulate(
            [float(models[(task, h)].predict_proba(X)[0, 1]) for h in hs]
        )

        first50 = next(
            (h for h, probability in zip(hs, p) if probability >= 0.5),
            None,
        )

        ref = p[hs.index(120)] if 120 in hs else p[-1]

        alerts = spec["alerts"]

    previous_level = (
         previous_levels.get(task)
        if previous_levels is not None
         else None
)

    level = choose_alert_level(
    probability=float(ref),
    alerts=alerts,
    previous_level=previous_level,
)

    reach = {
            str(int(threshold * 100)): reach_minutes(hs, p, threshold)
            for threshold in (0.3, 0.5, 0.7)
        }

    result = {
            **base,
            "status": "ok",
            "level": level,
            "risk_50_by_min": first50,
            "time_to_risk_min": reach,
            "risk": {
                str(h): round(float(probability), 4) for h, probability in zip(hs, p)
            },
        }

    if task in TIMING_EVENTS:
            result["timing_forecast"] = predict_timing(
                folder,
                task,
                feats,
            )

    out[task] = result

    return out


def load_timing_model(folder, task):
    if task not in TIMING_EVENTS:
        return None, None

    if folder.startswith("fold"):
        model_path = TIMING_DIR / folder / f"{task}.json"
    else:
        model_path = TIMING_DIR / f"{task}.json"

    meta_path = TIMING_DIR / f"{task}.meta.json"

    if not model_path.exists() or not meta_path.exists():
        return None, None

    key = (folder, task)

    if key not in TIMING_CACHE:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        model = xgb.XGBClassifier(enable_categorical=True)
        model.load_model(str(model_path))

        TIMING_CACHE[key] = (model, metadata)

    return TIMING_CACHE[key]


# predict time for the hike
def predict_timing(folder, task, feats):
    model, metadata = load_timing_model(folder, task)

    if model is None:
        return {
            "status": "unavailable",
            "reason": "timing_model_missing",
        }

    feature_names = metadata["features"]
    missing = [name for name in feature_names if name not in feats]

    if missing:
        return {
            "status": "unavailable",
            "reason": "missing_features",
            "missing": missing,
        }

    step = int(metadata["step_minutes"])
    max_minutes = int(metadata["max_minutes"])

    periods = np.arange(
        step,
        max_minutes + 1,
        step,
        dtype=np.float32,
    )

    base = frame(feats, feature_names)
    X = pd.concat(
        [base] * len(periods),
        ignore_index=True,
    )
    X["k_min"] = periods
    X = X[metadata["model_features"]]
    hazards = np.clip(
        model.predict_proba(X)[:, 1],
        0.0,
        1.0,
    )
    survival = np.cumprod(1.0 - hazards)
    cumulative = 1.0 - survival
    survival_before = np.concatenate(([1.0], survival[:-1]))
    event_mass = survival_before * hazards

    total_mass = float(event_mass.sum())

    expected_minutes = None
    median_minutes = None
    if total_mass > 1e-9:
        expected_minutes = int(round(float(np.dot(event_mass, periods) / total_mass)))
        conditional_cdf = np.cumsum(event_mass) / total_mass
        median_index = np.searchsorted(
            conditional_cdf,
            0.5,
        )
        median_minutes = int(periods[median_index])

    risk_curve = {
        str(int(minute)): round(float(probability), 4)
        for minute, probability in zip(periods, cumulative)
    }

    return {
        "status": "ok",
        "threshold": metadata["threshold"],
        "direction": metadata["direction"],
        "forecast_horizon_min": max_minutes,
        "event_probability_within_horizon": round(
            float(cumulative[-1]),
            4,
        ),
        "expected_minutes_if_event_within_horizon": expected_minutes,
        "median_minutes_if_event_within_horizon": median_minutes,
        "risk_curve": risk_curve,
        "note": (
            "Approximate timing estimates conditional on an event "
            "occurring within the forecast horizon. Not a guaranteed "
            "threshold-crossing time."
        ),
    }


def group_of(name):
    if name == "glucose":
        return "current glucose level"
    if name.startswith(
        (
            "min_since_",
            "glucose_mean_6h",
            "glucose_std_6h",
            "glucose_max_6h",
            "glucose_min_6h",
        )
    ):
        return "longer glucose history"
    if name.startswith("glucose"):
        return "recent glucose trend"
    if name.startswith(("hr_", "act_", "activity_calories")):
        return "heart rate and activity"
    if name.startswith("hour_"):
        return "time of day"
    return "meals"


def drivers_for(folder, task, feats, horizon=120):
    spec = TASKS[task]
    model = load_models(folder).get((task, horizon))
    if model is None or any(f not in feats for f in spec["features"]):
        return []
    X = frame(feats, spec["features"])
    booster = model.get_booster()
    names = booster.feature_names or spec["features"]
    contrib = booster.predict(
        xgb.DMatrix(X, enable_categorical=True), pred_contribs=True
    )[0][:-1]
    groups = {}
    for name, v in zip(names, contrib):
        g = group_of(name)
        groups[g] = groups.get(g, 0.0) + float(v)
    out = []
    for g, v in sorted(groups.items(), key=lambda kv: -abs(kv[1]))[:3]:
        if abs(v) >= 0.1:
            out.append(
                {
                    "factor": g,
                    "effect": "raises risk" if v > 0 else "lowers risk",
                    "strength": (
                        "strongly"
                        if abs(v) >= 1.0
                        else "moderately" if abs(v) >= 0.4 else "slightly"
                    ),
                }
            )
    return out


class Patient:
    def __init__(self, pid, folder, subject=None, tz=None, profile=None):
        self.pid, self.folder, self.subject, self.tz = pid, folder, subject, tz
        self.profile = profile or {}
        self.state = PatientState(CAPS, EVENTS, tz=tz)
        self.history = []
        self.alert_levels = {}

    def feats(self, t, extra=None):
        return {**self.state.features_at(t, extra=extra), **self.profile}

    
    def on_reading(self, t, do_predict):
        g = self.state.glucose_at(t)
        warming = not self.state.warm(t)
        hr, act = self.state.recent_wearable(t)

        entry = {
            "timestamp": from_minute(t).isoformat(),
            "t": t,
            "glucose": round(g, 1),
            "warming_up": warming,
            "predicted": False,
            "tasks": {},
            "signals": {
                "hr_bpm": None if np.isnan(hr) else int(round(float(hr))),
                "activity_level": None if np.isnan(act) else round(float(act), 1),
            },
        }

        if do_predict and not warming:
            entry["tasks"] = predict(
                self.folder,
                self.feats(t),
                g,
                previous_levels=self.alert_levels,
            )

            for task_name, task_result in entry["tasks"].items():
                if task_result.get("status") == "in_event":
                    self.alert_levels[task_name] = "alert"
                elif task_result.get("level") in {"ok", "watch", "alert"}:
                    self.alert_levels[task_name] = task_result["level"]

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

class ExplainIn(BaseModel):
    patient_id: str
    event: str = "overview"
    use_llm: bool = True
    meal: Optional[MealIn] = None

def meal_dict(m):
    return {
        "meal_type": m.meal_type,
        "calories": m.calories,
        "carbs": m.carbs,
        "protein": m.protein,
        "fat": m.fat,
        "fiber": m.fiber,
    }


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
    return {
        "horizons": HORIZONS,
        "tasks": {
            k: {kk: vv for kk, vv in v.items() if kk != "features"}
            | {"n_features": len(v["features"])}
            for k, v in TASKS.items()
        },
    }


@app.post("/reset")
def reset(req: ResetIn):
    folder = "final"
    if req.mode == "cv":
        if req.subject is None or str(req.subject) not in FOLD_OF:
            raise HTTPException(
                400, "mode 'cv' needs a subject id from the training data"
            )
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
        PATIENTS[req.patient_id] = Patient(
            req.patient_id, folder, req.subject, req.timezone, req.profile
        )
    return {
        "patient_id": req.patient_id,
        "model_folder": folder,
        "timezone": req.timezone,
    }


# send the data as real time flow like real life scenario


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
        last_t = p.history[-1]["t"] if p.history else -(10**12)
        made = late = 0
        for t in times:
            if t <= last_t:
                late += 1
                continue
            p.on_reading(t, req.do_predict)
            made += 1
        return {
            "patient_id": p.pid,
            "wearable": len(req.wearable),
            "glucose": len(req.glucose),
            "meals": len(req.meals),
            "new_readings": made,
            "late_readings": late,
            "latest": p.history[-1] if p.history else None,
        }


# patients report


@app.get("/patients")
def patients():
    return [
        {
            "patient_id": p.pid,
            "model_folder": p.folder,
            "subject": p.subject,
            "timezone": p.tz,
            "readings": len(p.history),
            "last": p.history[-1]["timestamp"] if p.history else None,
        }
        for p in PATIENTS.values()
    ]


@app.get("/patients/{pid}/latest")
def latest(pid: str):
    with LOCK:
        p = get_patient(pid)
        if not p.history:
            raise HTTPException(404, "no glucose readings yet")
        return {"model_folder": p.folder, "profile": p.profile, **p.history[-1]}
        # return {"model_folder": p.folder,  **p.history[-1]}


@app.get("/patients/{pid}/history")
def history(pid: str, limit: int = 400):
    with LOCK:
        return get_patient(pid).history[-limit:]


@app.get("/patients/{pid}/inspect")
def inspect(pid: str, timestamp: str, event: str = "high180"):
    if event not in EVENTS:
        raise HTTPException(400, f"unknown event {event}")
    with LOCK:
        p = get_patient(pid)
        try:
            t = p.state.minute(timestamp)
        except Exception:
            raise HTTPException(422, "bad timestamp")
        g = p.state.glucose_at(t)
        if np.isnan(g):
            raise HTTPException(404, "no glucose reading at that exact time")
        if not p.state.warm(t):
            raise HTTPException(409, "less than one hour of history at that time")
        feats = p.feats(t)
        tasks = predict(p.folder, feats, g)
        drivers = (
            drivers_for(p.folder, event, feats)
            if tasks[event].get("status") == "ok"
            else []
        )
    clean = {
        k: (None if isinstance(v, float) and np.isnan(v) else v)
        for k, v in feats.items()
    }
    return {
        "timestamp": timestamp,
        "glucose": g,
        "model_folder": p.folder,
        "features": clean,
        "tasks": tasks,
        "drivers": drivers,
    }


# here the code for whatif  function
@app.post("/whatif")
def whatif(req: WhatIfIn):
    with LOCK:
        p = get_patient(req.patient_id)
        if not p.history or p.history[-1]["warming_up"]:
            raise HTTPException(
                409, "patient needs at least one hour of glucose history"
            )
        last = p.history[-1]
        t = last["t"]
        g = p.state.glucose_at(t)
        extra = p.state.prepare_meal(t, meal_dict(req.meal))
        sim = predict(p.folder, p.feats(t, extra=extra), g)
        base = last["tasks"] if last["predicted"] else predict(p.folder, p.feats(t), g)
    return {
        "timestamp": last["timestamp"],
        "glucose": last["glucose"],
        "baseline": base,
        "with_meal": sim,
        "note": "Model estimate of how risk changes if this meal is logged now. "
        "It reflects patterns in the training data, not a causal or clinical prediction.",
    }


EXPLAIN_CACHE = {}


def pick_explanation_focus(tasks, event):
    if event != "overview":
        return event

    core = [
        key for key, task in tasks.items()
        if not task.get("exploratory")
    ] or list(tasks)

    active = [
        key for key in core
        if tasks[key].get("status") == "in_event"
    ]

    if active:
        return active[0]

    valid = [
        key for key in core
        if tasks[key].get("status") == "ok"
    ]

    if valid:
        return max(
            valid,
            key=lambda key: tasks[key]["risk"].get(
                "120", 0
            ),
        )

    if not core:
        raise HTTPException(
            503, "No prediction tasks are available"
        )

    return core[0]


@app.post("/explain")
def explain_endpoint(req: ExplainIn):
    if req.event != "overview" and req.event not in TASKS:
        raise HTTPException(
            400, f"Unknown event: {req.event}"
        )

    with LOCK:
        p = get_patient(req.patient_id)

        if not p.history or p.history[-1]["warming_up"]:
            raise HTTPException(
                409,
                "Patient needs at least one hour of glucose history",
            )

        last = p.history[-1]
        t = last["t"]
        glucose = p.state.glucose_at(t)
        features = p.feats(t)

        tasks = (
            last["tasks"]
            if last["predicted"]
            else predict(p.folder, features, glucose)
        )

        focus = pick_explanation_focus(tasks, req.event)

        if focus not in tasks:
            raise HTTPException(
                503, "No prediction is available for this event"
            )

        focus_task = tasks[focus]

        drivers = (
            drivers_for(p.folder, focus, features)
            if focus_task.get("status") == "ok"
            else []
        )

        what_if = None

        if req.meal is not None and focus_task.get("status") == "ok":
            extra = p.state.prepare_meal(
                t, meal_dict(req.meal)
            )

            simulated = predict(
                p.folder,
                p.feats(t, extra=extra),
                glucose,
            ).get(focus, {})

            if simulated.get("status") == "ok":
                current_risk = round(
                    focus_task["risk"]["120"] * 100
                )
                new_risk = round(
                    simulated["risk"]["120"] * 100
                )

                what_if = {
                    "meal_type": req.meal.meal_type,
                    "carbs_g": round(req.meal.carbs or 0),
                    "event": LABELS.get(focus, focus),
                    "risk_percent_2h_now": current_risk,
                    "risk_percent_2h_after_meal": new_risk,
                    "change_points": new_risk - current_risk,
                }

        facts = build_facts(
            last,
            features,
            tasks,
            focus,
            drivers,
            THRESHOLDS[focus],
            what_if,
        )

        cache_key = (
            req.patient_id,
            req.event,
            last["timestamp"],
            req.use_llm,
            json.dumps(
                meal_dict(req.meal),
                sort_keys=True,
            ) if req.meal else None,
        )

        cached = EXPLAIN_CACHE.get(cache_key)

        if cached is not None:
            return cached

    # Do not hold the patient-state lock during the AI request.
    result = explain_text(facts, use_llm=req.use_llm)

    response = {
        "patient_id": req.patient_id,
        "timestamp": last["timestamp"],
        "event": req.event,
        **result,
        "facts": facts,
    }

    EXPLAIN_CACHE[cache_key] = response
    return response


@app.get("/metrics")
def metrics():
    path = ROOT / "data" / "processed" / "train_oof_metrics.csv"
    if not path.exists():
        raise HTTPException(404, "train_oof_metrics.csv not found; run train_model.py")
    return json.loads(pd.read_csv(path).to_json(orient="records"))


@app.websocket("/ws/{pid}")
async def stream(websocket: WebSocket, pid: str):
    await websocket.accept()
    sent = None
    try:
        while True:
            p = PATIENTS.get(pid)
            if p is not None:
                n = len(p.history)
                if sent is None or n < sent or n - sent > 200:
                    await websocket.send_json(
                        {"type": "snapshot", "entries": p.history[-600:]}
                    )
                    sent = n
                elif n > sent:
                    await websocket.send_json(
                        {"type": "readings", "entries": p.history[sent:n]}
                    )
                    sent = n
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        pass
