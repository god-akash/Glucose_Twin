import bisect

import numpy as np
import pandas as pd

EPOCH = pd.Timestamp("1970-01-01")
STEP = 15
PAST_STEPS = 24
LAGS = [1, 2, 3, 4, 6, 8, 12, 16]
CAP_SINCE = 1440
MACROS = ["calories", "carbs", "protein", "fat", "fiber"]


def to_minute(ts, tz=None):
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        if tz is None:
            raise ValueError("timezone-aware timestamp but no patient timezone is set")
        ts = ts.tz_convert(tz).tz_localize(None)
    return int((ts - EPOCH).total_seconds() // 60)


def from_minute(m):
    return EPOCH + pd.Timedelta(minutes=int(m))


def _f(x):
    return np.nan if x is None else float(x)


def norm_meal(x):
    x = str(x or "").strip().lower()
    for name in ("breakfast", "lunch", "dinner"):
        if x.startswith(name[:5]):
            return name
    return "snack"


def _mean(a):
    a = a[~np.isnan(a)]
    return float(a.mean()) if len(a) else np.nan


class PatientState:
    def __init__(self, caps, events, tz=None, tol=0):
        self.caps, self.events, self.tz, self.tol = caps, events, tz, tol
        self.g_ts, self.g_val = [], []
        self.w_ts, self.w_hr, self.w_act, self.w_cal = [], [], [], []
        self.meal_ts, self.meals = [], []

    def minute(self, ts):
        return to_minute(ts, self.tz)

    def add_glucose(self, ts, value):
        t = self.minute(ts)
        i = bisect.bisect_left(self.g_ts, t)
        if i < len(self.g_ts) and self.g_ts[i] == t:
            self.g_val[i] = float(value)
        else:
            self.g_ts.insert(i, t)
            self.g_val.insert(i, float(value))
        return t

    def add_wearable(self, ts, hr=None, act=None, cal=None):
        t = self.minute(ts)
        i = bisect.bisect_left(self.w_ts, t)
        if i < len(self.w_ts) and self.w_ts[i] == t:
            for arr, v in ((self.w_hr, hr), (self.w_act, act), (self.w_cal, cal)):
                if v is not None and not np.isnan(v):
                    arr[i] = float(v)
        else:
            self.w_ts.insert(i, t)
            self.w_hr.insert(i, _f(hr))
            self.w_act.insert(i, _f(act))
            self.w_cal.insert(i, _f(cal))
        return t

    def prepare_meal(self, t, meal):
        v = {k: _f(meal.get(k)) for k in MACROS}
        for k in MACROS:
            if not np.isnan(v[k]):
                v[k] = min(v[k], self.caps[k])
        v["fiber"] = float(np.fmin(v["fiber"], v["carbs"]))
        v["t"], v["type"] = t, norm_meal(meal.get("meal_type"))
        return v

    def add_meal(self, ts, meal):
        t = self.minute(ts)
        i = bisect.bisect_right(self.meal_ts, t)
        self.meal_ts.insert(i, t)
        self.meals.insert(i, self.prepare_meal(t, meal))
        return t

    def glucose_at(self, t):
        i = bisect.bisect_left(self.g_ts, t)
        best = None
        for j in (i - 1, i):
            if 0 <= j < len(self.g_ts) and abs(self.g_ts[j] - t) <= self.tol:
                if best is None or abs(self.g_ts[j] - t) < abs(self.g_ts[best] - t):
                    best = j
        return self.g_val[best] if best is not None else np.nan

    def warm(self, t):
        return all(not np.isnan(self.glucose_at(t - STEP * k)) for k in range(5))

    def recent_wearable(self, t):
        hi = bisect.bisect_right(self.w_ts, t)
        lo = bisect.bisect_right(self.w_ts, t - 15)
        return (_mean(np.array(self.w_hr[lo:hi], dtype=float)),
                _mean(np.array(self.w_act[lo:hi], dtype=float)))

    def features_at(self, t, extra=None):
        p = np.array([self.glucose_at(t - STEP * k) for k in range(PAST_STEPS + 1)], dtype=float)
        f = {"glucose": p[0]}
        for k in LAGS:
            f[f"glucose_lag_{k * STEP}"] = p[k]
        f["glucose_change_15"] = p[0] - p[1]
        f["glucose_change_30"] = p[0] - p[2]
        f["glucose_change_60"] = p[0] - p[4]
        for label, w in (("2h", 9), ("6h", PAST_STEPS + 1)):
            f[f"glucose_mean_{label}"] = float(np.nanmean(p[:w]))
            f[f"glucose_std_{label}"] = float(np.nanstd(p[:w]))
            f[f"glucose_max_{label}"] = float(np.nanmax(p[:w]))
            f[f"glucose_min_{label}"] = float(np.nanmin(p[:w]))

        n = bisect.bisect_right(self.g_ts, t)
        gt, gv = np.array(self.g_ts[:n]), np.array(self.g_val[:n])
        for name, (thr, direction) in self.events.items():
            idx = np.flatnonzero(gv > thr if direction == "above" else gv < thr)
            f[f"min_since_{name}"] = float(min(t - gt[idx[-1]], CAP_SINCE)) if len(idx) else float(CAP_SINCE)

        hi = bisect.bisect_right(self.w_ts, t)

        def win(w, series):
            lo = bisect.bisect_right(self.w_ts, t - w)
            return np.array(series[lo:hi], dtype=float)

        hr15, hr60 = win(15, self.w_hr), win(60, self.w_hr)
        a15, a60 = win(15, self.w_act), win(60, self.w_act)
        c60 = win(60, self.w_cal)
        f["hr_mean_15"] = _mean(hr15)
        f["hr_mean_60"] = _mean(hr60)
        v60 = hr60[~np.isnan(hr60)]
        f["hr_std_60"] = float(v60.std(ddof=1)) if len(v60) >= 2 else np.nan
        f["hr_observed_15"] = float((~np.isnan(hr15)).mean()) if len(hr15) else np.nan
        f["act_level_mean_15"] = _mean(a15)
        f["act_level_mean_60"] = _mean(a60)
        av = a60[~np.isnan(a60)]
        f["act_active_frac_60"] = float((av >= 1).mean()) if len(av) else np.nan
        cv = c60[~np.isnan(c60)]
        f["activity_calories_60"] = float(cv.sum()) if len(cv) else np.nan

        meals = self.meals[:bisect.bisect_right(self.meal_ts, t)] + ([extra] if extra else [])
        if meals:
            last = meals[-1]
            f["minutes_since_meal"] = float(min(t - last["t"], 480))
            f["last_meal_type"] = last["type"]
            for k in MACROS:
                f[f"last_{k}_full"] = last[k]
        else:
            f["minutes_since_meal"] = 480.0
            f["last_meal_type"] = "none"
            for k in MACROS:
                f[f"last_{k}_full"] = np.nan
        for h in (1, 2, 4):
            f[f"carbs_full_{h}h"] = float(sum(np.nan_to_num(m["carbs"]) for m in meals if t - 60 * h < m["t"] <= t))

        d = from_minute(t)
        hod = d.hour + d.minute / 60
        f["hour_sin"] = float(np.sin(2 * np.pi * hod / 24))
        f["hour_cos"] = float(np.cos(2 * np.pi * hod / 24))
        return f

        