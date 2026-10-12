import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

RAW = Path("data/raw/cgmacros")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

STEP = 15
MAX_H = 360
K = MAX_H // STEP

FUTURE_HORIZONS = list(range(STEP, MAX_H + 1, STEP))
RISK_HORIZONS = [30, 60, 90, 120, 180, 240, 300, 360]

PAST_STEPS = 24
LAG_STEPS = [1, 2, 3, 4, 6, 8, 12, 16]

CAP_SINCE = 1440
MIN_KNOTS = 4

EVENTS = {
    "high140": (140, "above"),
    "high180": (180, "above"),
    "low70": (70, "below"),
}

MACROS = [
    "Calories",
    "Carbs",
    "Protein",
    "Fat",
    "Fiber",
]

LCS = [c.lower() for c in MACROS]

DOC_MAX = {
    "calories": 1180,
    "carbs": 176,
    "protein": 176,
    "fat": 176,
    "fiber": 60,
}

SMALL_POLICY = "unknown"
EXCLUDE_SUBJECTS = {7}
MERGE_INTENSITY = True

EPOCH = pd.Timestamp("1970-01-01")


CANON = {
    "timestamp": "Timestamp",
    "libregl": "Libre GL",
    "dexcomgl": "Dexcom GL",
    "hr": "HR",
    "caloriesactivity": "Calories (Activity)",
    "activitycalories": "Calories (Activity)",
    "mets": "METs",
    "intensity": "Intensity",
    "mealtype": "Meal Type",
    "calories": "Calories",
    "carbs": "Carbs",
    "protein": "Protein",
    "fat": "Fat",
    "fiber": "Fiber",
    "amountconsumed": "Amount Consumed",
    "imagepath": "Image path",
}

REQUIRED = [
    "Timestamp",
    "Libre GL",
    "HR",
    "Calories (Activity)",
    "METs",
    "Meal Type",
    "Calories",
    "Carbs",
    "Protein",
    "Fat",
    "Fiber",
    "Amount Consumed",
]

KNOWN = (
    set(REQUIRED)
    | {
        "Dexcom GL",
        "Image path",
        "Unnamed: 0",
        "Intensity",
        "Steps",
        "RecordIndex",
        "Sugar",
    }
)


def to_min(ts):
    return (
        (ts - EPOCH)
        .dt.total_seconds()
        // 60
    ).astype("int64").to_numpy()


def normalize_meal(x):
    x = str(x).strip().lower()

    if x.startswith("breakfast"):
        return "breakfast"

    if x.startswith("lunch"):
        return "lunch"

    if x.startswith("dinner"):
        return "dinner"

    return "snack"


def canonicalize(df):
    names = []

    for column in df.columns:
        key = re.sub(
            r"[^a-z0-9]",
            "",
            str(column).lower(),
        )

        names.append(
            CANON.get(
                key,
                str(column).strip(),
            )
        )

    df = df.copy()
    df.columns = names

    return df.loc[
        :,
        ~df.columns.duplicated(),
    ]


def add_activity_level(df):
    if "METs" not in df.columns:
        df["METs"] = np.nan

    if "Intensity" not in df.columns:
        df["Intensity"] = np.nan

    mets = (
        df["METs"]
        .to_numpy(dtype=float)
        / 10.0
    )

    derived = np.select(
        [
            mets <= 1.5,
            mets <= 6.0,
        ],
        [
            0,
            1,
        ],
        default=2,
    ).astype(float)

    derived[np.isnan(mets)] = np.nan

    intensity = (
        df["Intensity"]
        .to_numpy(dtype=float)
    )

    native = np.select(
        [
            intensity <= 0,
            intensity <= 2,
        ],
        [
            0,
            1,
        ],
        default=2,
    ).astype(float)

    native[np.isnan(intensity)] = np.nan

    if MERGE_INTENSITY:
        df["act_level"] = np.where(
            np.isnan(derived),
            native,
            derived,
        )
    else:
        df["act_level"] = derived

    return df


def normalize_amount(raw, small_policy):
    a = np.asarray(
        raw,
        dtype=float,
    )

    ok = ~np.isnan(a)

    conditions = [
        ok & (a == 0),
        ok & (a > 0) & (a < 1),
        ok & (a >= 1) & (a <= 4),
        ok & (a > 4) & (a < 100),
        ok & (a == 100),
        ok & (a > 100),
    ]

    names = [
        "zero",
        "sub1",
        "small_1_4",
        "mid_5_99",
        "full_100",
        "div10",
    ]

    rule = np.select(
        conditions,
        names,
        default="missing",
    )

    pct = a.copy()

    big = ok & (a > 100)
    pct[big] = a[big] / 10.0

    known = ok.copy()

    if small_policy == "unknown":
        small = (
            ok
            & (a > 0)
            & (a <= 4)
        )

        pct[small] = 100.0
        known = ok & ~small

    return (
        np.clip(
            pct,
            0,
            100,
        ),
        rule,
        known,
    )


def read_meals(
    df,
    subject,
    keep_zero=False,
):
    m = (
        df[
            df["Meal Type"].notna()
        ]
        .reset_index(drop=True)
    )

    raw_amount = pd.to_numeric(
        m["Amount Consumed"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    pct, rule, known = normalize_amount(
        raw_amount,
        SMALL_POLICY,
    )

    pct_literal, _, _ = normalize_amount(
        raw_amount,
        "literal",
    )

    pct_assume_full, _, _ = normalize_amount(
        raw_amount,
        "unknown",
    )

    out = pd.DataFrame({
        "subject": subject,
        "timestamp": m["Timestamp"],
        "meal_type": m["Meal Type"].map(
            normalize_meal
        ),
        "amount_raw": raw_amount,
        "amount_rule": rule,
        "amount_known": known.astype(int),
        "fraction_eaten": np.where(
            known,
            pct / 100.0,
            1.0,
        ),
        "fraction_literal": np.where(
            ~np.isnan(raw_amount),
            pct_literal / 100.0,
            1.0,
        ),
        "fraction_assume_full": np.where(
            ~np.isnan(raw_amount),
            pct_assume_full / 100.0,
            1.0,
        ),
    })

    for column in MACROS:
        out[
            f"{column.lower()}_full_raw"
        ] = pd.to_numeric(
            m[column],
            errors="coerce",
        ).to_numpy(
            dtype=float
        )

    if not keep_zero:
        out = out[
            out["amount_rule"] != "zero"
        ]

    return (
        out
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def finalize_meals(meals):
    meals = meals.copy()

    for lc in LCS:
        meals[f"{lc}_full"] = (
            meals[f"{lc}_full_raw"]
            .clip(upper=CAPS[lc])
        )

    meals["fiber_full"] = np.minimum(
        meals["fiber_full"],
        60
    )

    meals["fiber_full"] = np.minimum(
        meals["fiber_full"],
        meals["carbs_full"]
    )

    for lc in LCS:
        meals[f"{lc}_eaten"] = (
            meals[f"{lc}_full"]
            * meals["fraction_eaten"]
        )

    return meals


def meal_response(
    meal_minutes,
    glucose_minutes,
    glucose,
):
    baseline = np.full(
        len(meal_minutes),
        np.nan,
    )

    peak = np.full(
        len(meal_minutes),
        np.nan,
    )

    for i, meal_time in enumerate(
        meal_minutes
    ):
        base_idx = np.searchsorted(
            glucose_minutes,
            meal_time,
            side="right",
        ) - 1

        if base_idx < 0:
            continue

        if (
            meal_time
            - glucose_minutes[base_idx]
            > STEP
        ):
            continue

        start = np.searchsorted(
            glucose_minutes,
            meal_time,
            side="right",
        )

        end = np.searchsorted(
            glucose_minutes,
            meal_time + 120,
            side="right",
        )

        window = glucose[
            start:end
        ]

        if len(window) >= 6:
            baseline[i] = glucose[base_idx]
            peak[i] = np.nanmax(window)

    return baseline, peak


def time_to_event(
    name,
    threshold,
    direction,
    glucose,
    future,
):
    missing = np.isnan(
        future
    )

    follow = np.where(
        missing.any(axis=1),
        missing.argmax(axis=1),
        K,
    )

    if direction == "above":
        hit = future > threshold
    else:
        hit = future < threshold

    hit &= (
        np.arange(K)[None, :]
        < follow[:, None]
    )

    has_event = hit.any(
        axis=1
    )

    first = (
        hit.argmax(axis=1)
        + 1
    )

    tte = np.where(
        has_event,
        first,
        follow,
    ) * STEP

    follow_min = follow * STEP

    if direction == "above":
        at_risk = (
            glucose <= threshold
        )
    else:
        at_risk = (
            glucose >= threshold
        )

    result = {
        f"{name}_tte": tte,
        f"{name}_event":
            has_event.astype(int),
        f"{name}_follow":
            follow_min,
        f"{name}_at_risk":
            at_risk.astype(int),
        f"{name}_usable":
            (
                at_risk
                & (follow >= 1)
            ).astype(int),
    }

    for horizon in RISK_HORIZONS:
        result[
            f"{name}_within_{horizon}"
        ] = np.where(
            has_event
            & (tte <= horizon),
            1.0,
            np.where(
                follow_min >= horizon,
                0.0,
                np.nan,
            ),
        )

    return result


def spearman(a, b):
    d = pd.DataFrame({
        "a": np.asarray(
            a,
            dtype=float,
        ),
        "b": np.asarray(
            b,
            dtype=float,
        ),
    }).dropna()

    if len(d) < 10:
        return np.nan

    return d[
        "a"
    ].rank().corr(
        d["b"].rank()
    )


bio = pd.read_csv(
    RAW / "bio.csv"
)

bio.columns = (
    bio.columns
    .str.strip()
)


def num(column):
    return pd.to_numeric(
        bio[column],
        errors="coerce",
    )


static = pd.DataFrame({
    "subject": bio[
        "subject"
    ].astype(int),

    "age": num("Age"),

    "sex_male": (
        bio["Gender"]
        .astype(str)
        .str.strip()
        .str.upper()
        == "M"
    ).astype(int),

    "bmi": num("BMI"),

    "hba1c": num(
        "A1c PDL (Lab)"
    ),

    "fasting_glucose": num(
        "Fasting GLU - PDL (Lab)"
    ),

    "insulin": num(
        "Insulin"
    ),

    "triglycerides_log": np.log1p(
        num("Triglycerides")
        .clip(lower=0)
    ),

    "total_cholesterol": num(
        "Cholesterol"
    ),

    "hdl": num(
        "HDL"
    ),
})

static["homa_ir"] = (
    static["fasting_glucose"]
    * static["insulin"]
    / 405.0
)

static_columns = [
    c
    for c in static.columns
    if c != "subject"
]


raw = {}
schema_issues = {}
sensor_bias = {}

for folder in sorted(
    RAW.glob("CGMacros-*")
):
    file = (
        folder
        / f"{folder.name}.csv"
    )

    subject = int(
        folder.name.split("-")[1]
    )

    if subject in EXCLUDE_SUBJECTS:
        print(
            f"excluded participant "
            f"{subject:03d} "
            f"(EXCLUDE_SUBJECTS)"
        )
        continue

    if not file.exists():
        print(
            "Missing:",
            file,
        )
        continue

    df = canonicalize(
        pd.read_csv(
            file,
            low_memory=False,
        )
    )

    missing = [
        c
        for c in REQUIRED
        if c not in df.columns
    ]

    extra = [
        c
        for c in df.columns
        if c not in KNOWN
    ]

    if missing or extra:
        schema_issues[
            subject
        ] = {
            "missing": missing,
            "unexpected": extra,
        }

    assert (
        "Timestamp" in df.columns
        and "Libre GL" in df.columns
    ), (
        f"{file}: "
        f"no Timestamp/Libre GL"
    )

    for column in missing:
        df[column] = np.nan

    for column in [
        "HR",
        "Calories (Activity)",
        "METs",
        "Dexcom GL",
        "Intensity",
    ]:
        if column not in df.columns:
            df[column] = np.nan

    for column in [
        "Libre GL",
        "Dexcom GL",
        "HR",
        "Calories (Activity)",
        "METs",
        "Intensity",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"],
        errors="coerce",
    )

    df = (
        df
        .dropna(
            subset=["Timestamp"]
        )
        .sort_values("Timestamp")
        .drop_duplicates(
            "Timestamp"
        )
        .reset_index(drop=True)
    )

    df = add_activity_level(
        df
    )

    sensor_bias[subject] = float(
        (
            df["Libre GL"]
            - df["Dexcom GL"]
        ).mean()
    )

    raw[subject] = df


order = (
    static[
        static["subject"]
        .isin(raw)
    ]
    .sort_values("hba1c")[
        "subject"
    ]
    .tolist()
)

fold_of = {
    subject: i % 5
    for i, subject in enumerate(order)
}


print(
    "\n=== COLUMN LAYOUT CHECK "
    "(missing / unexpected columns) ==="
)

if schema_issues:

    for subject, info in (
        schema_issues.items()
    ):
        print(
            f"participant "
            f"{subject:03d}: "
            f"missing={info['missing']} "
            f"unexpected={info['unexpected']}"
        )

else:
    print(
        "all participant files "
        "match the standard layout"
    )


print(
    "\n=== ACTIVITY LEVEL CHECK ==="
)

parts = []

for subject, df in raw.items():

    if df["METs"].notna().any():
        group = "METs-derived"
    elif df["Intensity"].notna().any():
        group = "native Intensity"
    else:
        group = "none"

    parts.append(
        pd.DataFrame({
            "group": group,
            "level": df["act_level"],
            "hr": df["HR"],
        })
    )

activity_table = (
    pd.concat(
        parts,
        ignore_index=True,
    )
    .dropna(
        subset=["level"]
    )
)

table = (
    activity_table
    .groupby(
        ["group", "level"]
    )
    .agg(
        minutes=("hr", "size"),
        median_hr=("hr", "median"),
    )
)

table["share_%"] = (
    100
    * table["minutes"]
    / table.groupby(
        level=0
    )["minutes"].transform("sum")
)

print(
    table.round(1).to_string()
)

print(
    "\nLevels:"
    "\n0 = sedentary"
    "\n1 = light/moderate"
    "\n2 = vigorous"
)


with_zero = pd.concat(
    [
        read_meals(
            df,
            subject,
            keep_zero=True,
        )
        for subject, df
        in raw.items()
    ],
    ignore_index=True,
)

kept = with_zero[
    with_zero["amount_rule"]
    != "zero"
]

CAPS = {
    lc: min(
        float(
            kept[
                f"{lc}_full_raw"
            ].quantile(0.99)
        ),
        DOC_MAX[lc],
    )
    for lc in LCS
}

print(
    "\nMacro caps:",
    {
        k: round(v, 1)
        for k, v in CAPS.items()
    },
)

print(
    "meals clipped:",
    {
        lc: int(
            (
                kept[
                    f"{lc}_full_raw"
                ]
                > CAPS[lc]
            ).sum()
        )
        for lc in LCS
    },
)


print(
    "\n=== Amount Consumed "
    "normalization ==="
)

print(
    with_zero[
        "amount_rule"
    ]
    .value_counts()
    .to_string()
)

print(
    "small-code policy:",
    SMALL_POLICY,
)


def build_subject(
    subject,
    df,
):

    t_all = to_min(
        df["Timestamp"]
    )

    g_raw = df[
        "Libre GL"
    ].to_numpy(
        dtype=float
    )

    gap = (
        df["Timestamp"]
        .diff()
        .dt.total_seconds()
        .div(60)
    )

    segments = (
        gap > 5
    ).cumsum().to_numpy()

    is_knot = np.zeros(
        len(df),
        dtype=bool,
    )

    if len(df) > 2:

        is_knot[1:-1] = (
            np.abs(
                np.diff(
                    g_raw,
                    n=2,
                )
            )
            > 1e-6
        )

    keep = np.zeros(
        len(df),
        dtype=bool,
    )

    used = 0
    total = 0

    for segment in np.unique(
        segments
    ):

        idx = np.where(
            segments == segment
        )[0]

        knots = idx[
            is_knot[idx]
        ]

        total += len(knots)

        if len(knots) < MIN_KNOTS:
            continue

        offsets = (
            t_all[knots]
            % STEP
        )

        if len(offsets) >= 3:

            odd = np.zeros(
                len(offsets),
                dtype=bool,
            )

            odd[1:-1] = (
                (
                    offsets[1:-1]
                    != offsets[:-2]
                )
                &
                (
                    offsets[:-2]
                    == offsets[2:]
                )
            )

            knots = knots[
                ~odd
            ]

            offsets = offsets[
                ~odd
            ]

        cuts = np.flatnonzero(
            np.diff(offsets)
            != 0
        ) + 1

        starts = np.r_[
            0,
            cuts,
        ]

        ends = np.r_[
            cuts,
            len(offsets),
        ]

        for start, end in zip(
            starts,
            ends,
        ):

            if (
                end - start
                < MIN_KNOTS
            ):
                continue

            rows = np.arange(
                knots[start],
                knots[end - 1] + 1,
            )

            keep[rows] = (
                t_all[rows]
                % STEP
                == offsets[start]
            )

            used += (
                end - start
            )

    keep &= ~np.isnan(
        g_raw
    )

    grid = (
        df.loc[
            keep,
            [
                "Timestamp",
                "Libre GL",
            ],
        ]
        .rename(
            columns={
                "Timestamp": "timestamp",
                "Libre GL": "glucose",
            }
        )
        .reset_index(drop=True)
    )

    if grid.empty:
        return None, None, None

    ts = grid[
        "timestamp"
    ]

    glucose = grid[
        "glucose"
    ].to_numpy(
        dtype=float
    )

    g_min = to_min(ts)

    gseries = (
        grid
        .set_index(
            "timestamp"
        )["glucose"]
    )

    n = len(ts)

    def glucose_at(
        minutes
    ):
        return (
            gseries
            .reindex(
                ts
                + pd.Timedelta(
                    minutes=minutes
                )
            )
            .to_numpy()
        )

    cols = {
        "subject": subject,
        "timestamp": ts,
        "glucose": glucose,
    }


    past = np.column_stack(
        [
            glucose_at(
                -k * STEP
            )
            for k in range(
                PAST_STEPS + 1
            )
        ]
    )

    for k in LAG_STEPS:

        cols[
            f"glucose_lag_{k * STEP}"
        ] = past[:, k]

    cols[
        "glucose_change_15"
    ] = glucose - past[:, 1]

    cols[
        "glucose_change_30"
    ] = glucose - past[:, 2]

    cols[
        "glucose_change_60"
    ] = glucose - past[:, 4]

    for label, width in [
        ("2h", 9),
        (
            "6h",
            PAST_STEPS + 1,
        ),
    ]:

        cols[
            f"glucose_mean_{label}"
        ] = np.nanmean(
            past[:, :width],
            axis=1,
        )

        cols[
            f"glucose_std_{label}"
        ] = np.nanstd(
            past[:, :width],
            axis=1,
        )

        cols[
            f"glucose_max_{label}"
        ] = np.nanmax(
            past[:, :width],
            axis=1,
        )

        cols[
            f"glucose_min_{label}"
        ] = np.nanmin(
            past[:, :width],
            axis=1,
        )


    for name, (
        threshold,
        direction,
    ) in EVENTS.items():

        if direction == "above":
            condition = (
                glucose > threshold
            )
        else:
            condition = (
                glucose < threshold
            )

        event_minutes = (
            g_min[condition]
        )

        if len(event_minutes):

            pos = np.searchsorted(
                event_minutes,
                g_min,
                side="right",
            ) - 1

            safe_pos = np.clip(
                pos,
                0,
                None,
            )

            since = np.where(
                pos >= 0,
                g_min
                - event_minutes[
                    safe_pos
                ],
                CAP_SINCE,
            )

        else:

            since = np.full(
                n,
                CAP_SINCE,
            )

        cols[
            f"min_since_{name}"
        ] = np.minimum(
            since,
            CAP_SINCE,
        )


    w = df.set_index(
        "Timestamp"
    )

    for column, name in [
        ("HR", "hr"),
        ("METs", "mets"),
        (
            "act_level",
            "act_level",
        ),
    ]:

        for window in [
            15,
            60,
        ]:

            cols[
                f"{name}_mean_{window}"
            ] = (
                w[column]
                .rolling(
                    f"{window}min"
                )
                .mean()
                .reindex(ts)
                .to_numpy()
            )

    active = (
        w["act_level"] >= 1
    ).astype(float).where(
        w["act_level"].notna()
    )

    cols[
        "act_active_frac_60"
    ] = (
        active
        .rolling("60min")
        .mean()
        .reindex(ts)
        .to_numpy()
    )

    cols[
        "hr_std_60"
    ] = (
        w["HR"]
        .rolling("60min")
        .std()
        .reindex(ts)
        .to_numpy()
    )

    cols[
        "activity_calories_60"
    ] = (
        w[
            "Calories (Activity)"
        ]
        .rolling("60min")
        .sum()
        .reindex(ts)
        .to_numpy()
    )

    cols[
        "hr_observed_15"
    ] = (
        w["HR"]
        .notna()
        .astype(float)
        .rolling("15min")
        .mean()
        .reindex(ts)
        .to_numpy()
    )


    meals = finalize_meals(
        read_meals(
            df,
            subject,
        )
    )

    if len(meals):

        m_min = to_min(
            meals["timestamp"]
        )

        pos = np.searchsorted(
            m_min,
            g_min,
            side="right",
        ) - 1

        has = pos >= 0

        p = np.clip(
            pos,
            0,
            len(meals) - 1,
        )

        cols[
            "minutes_since_meal"
        ] = np.where(
            has,
            np.minimum(
                g_min
                - m_min[p],
                480,
            ),
            480,
        )

        cols[
            "last_amount_known"
        ] = np.where(
            has,
            meals[
                "amount_known"
            ].to_numpy()[p],
            np.nan,
        )

        cols[
            "last_fraction_eaten"
        ] = np.where(
            has,
            meals[
                "fraction_eaten"
            ].to_numpy()[p],
            np.nan,
        )

        for lc in LCS:

            cols[
                f"last_{lc}_full"
            ] = np.where(
                has,
                meals[
                    f"{lc}_full"
                ].to_numpy()[p],
                np.nan,
            )

            cols[
                f"last_{lc}_eaten"
            ] = np.where(
                has,
                meals[
                    f"{lc}_eaten"
                ].to_numpy()[p],
                np.nan,
            )

        cols[
            "last_meal_type"
        ] = np.where(
            has,
            meals[
                "meal_type"
            ].to_numpy()[p],
            "none",
        )

        hi = np.searchsorted(
            m_min,
            g_min,
            side="right",
        )

        sums = [
            (
                f"{lc}_eaten",
                meals[
                    f"{lc}_eaten"
                ],
            )
            for lc in LCS
        ]

        sums.append(
            (
                "carbs_full",
                meals[
                    "carbs_full"
                ],
            )
        )

        for name, series in sums:

            values = (
                series
                .fillna(0)
                .to_numpy(
                    dtype=float
                )
            )

            cumulative = np.concatenate(
                [
                    [0.0],
                    np.cumsum(values),
                ]
            )

            for hours in [
                1,
                2,
                4,
            ]:

                left = np.searchsorted(
                    m_min,
                    g_min
                    - hours * 60,
                    side="right",
                )

                cols[
                    f"{name}_{hours}h"
                ] = (
                    cumulative[hi]
                    - cumulative[left]
                )

        base, peak = meal_response(
            m_min,
            g_min,
            glucose,
        )

        meals[
            "base_glucose"
        ] = base

        meals[
            "peak_glucose_2h"
        ] = peak

        meals[
            "rise_2h"
        ] = peak - base

    else:

        cols[
            "minutes_since_meal"
        ] = np.full(
            n,
            480,
        )

        cols[
            "last_amount_known"
        ] = np.full(
            n,
            np.nan,
        )

        cols[
            "last_fraction_eaten"
        ] = np.full(
            n,
            np.nan,
        )

        for lc in LCS:

            cols[
                f"last_{lc}_full"
            ] = np.full(
                n,
                np.nan,
            )

            cols[
                f"last_{lc}_eaten"
            ] = np.full(
                n,
                np.nan,
            )

        cols[
            "last_meal_type"
        ] = np.full(
            n,
            "none",
        )

        for lc in LCS:

            for hours in [
                1,
                2,
                4,
            ]:

                cols[
                    f"{lc}_eaten_{hours}h"
                ] = np.zeros(n)

        for hours in [
            1,
            2,
            4,
        ]:

            cols[
                f"carbs_full_{hours}h"
            ] = np.zeros(n)

        meals = pd.DataFrame()


    hour = (
        ts.dt.hour
        + ts.dt.minute / 60
    )

    cols[
        "hour_sin"
    ] = np.sin(
        2 * np.pi * hour / 24
    )

    cols[
        "hour_cos"
    ] = np.cos(
        2 * np.pi * hour / 24
    )


    future = np.column_stack(
        [
            glucose_at(h)
            for h in FUTURE_HORIZONS
        ]
    )

    for i, horizon in enumerate(
        FUTURE_HORIZONS
    ):

        cols[
            f"target_{horizon}"
        ] = future[:, i]

    for name, (
        threshold,
        direction,
    ) in EVENTS.items():

        cols.update(
            time_to_event(
                name,
                threshold,
                direction,
                glucose,
                future,
            )
        )


    out = pd.DataFrame(
        cols
    )

    out = out.loc[
        ~np.isnan(
            past[:, 1:5]
        ).any(axis=1)
    ].reset_index(
        drop=True
    )

    info = {
        "subject": subject,
        "segments": len(
            np.unique(
                segments
            )
        ),
        "knots_used_%": (
            round(
                100 * used / total,
                1,
            )
            if total
            else np.nan
        ),
        "rows": len(out),
        "days": round(
            len(out) * STEP / 1440,
            1,
        ),
        "meals": len(meals),
        "libre_minus_dexcom": round(
            sensor_bias.get(
                subject,
                np.nan,
            ),
            1,
        ),
    }

    for name in EVENTS:

        info[
            f"{name}_events"
        ] = int(
            (
                (
                    out[
                        f"{name}_usable"
                    ] == 1
                )
                &
                (
                    out[
                        f"{name}_event"
                    ] == 1
                )
            ).sum()
        )

    return (
        out,
        info,
        meals,
    )


frames = []
infos = []
meal_frames = []

for subject, df in raw.items():

    result, info, meals = (
        build_subject(
            subject,
            df,
        )
    )

    if result is not None:

        frames.append(
            result
        )

        infos.append(
            info
        )

        if len(meals):
            meal_frames.append(
                meals
            )


if not frames:
    raise RuntimeError(
        "No participant data was processed."
    )


data = (
    pd.concat(
        frames,
        ignore_index=True,
    )
    .merge(
        static,
        on="subject",
        how="left",
    )
)

data["fold"] = (
    data["subject"]
    .map(fold_of)
)

meals_all = pd.concat(
    meal_frames,
    ignore_index=True,
)


assert data[
    "fold"
].notna().all()

assert (
    data[
        "minutes_since_meal"
    ] >= 0
).all()

assert (
    data
    .groupby(
        "subject"
    )["timestamp"]
    .apply(
        lambda x:
        x.is_monotonic_increasing
    )
    .all()
)

assert (
    meals_all[
        "fraction_eaten"
    ]
    .between(
        0,
        1,
    )
    .all()
)

assert (
    meals_all[
        "fiber_full"
    ].fillna(0)
    <=
    meals_all[
        "carbs_full"
    ].fillna(1e9)
    + 1e-9
).all()


for name in EVENTS:

    for h1, h2 in zip(
        RISK_HORIZONS[:-1],
        RISK_HORIZONS[1:],
    ):

        a = data[
            f"{name}_within_{h1}"
        ]

        b = data[
            f"{name}_within_{h2}"
        ]

        both = (
            a.notna()
            & b.notna()
        )

        assert (
            a[both] <= b[both]
        ).all()


def pick(*prefixes):
    return [
        c
        for c in data.columns
        if c.startswith(
            prefixes
        )
    ]


def uniq(seq):
    return list(
        dict.fromkeys(seq)
    )


meals_logged = uniq(
    [
        "minutes_since_meal",
        "last_meal_type",
    ]
    + [
        c
        for c in data.columns
        if (
            c.startswith("last_")
            and c.endswith("_full")
        )
    ]
    + pick(
        "carbs_full_"
    )
)


meals_consumed = uniq(
    [
        "last_amount_known",
        "last_fraction_eaten",
    ]
    + [
        c
        for c in data.columns
        if (
            c.startswith("last_")
            and c.endswith("_eaten")
        )
    ]
    + [
        c
        for c in data.columns
        if "_eaten_" in c
    ]
)


event_prefixes = tuple(
    f"{event}_"
    for event in EVENTS
)


groups = {

    "glucose": pick(
        "glucose",
        "min_since_",
    ),

    "wearable": pick(
        "hr_",
        "act_",
        "activity_calories",
    ),

    "wearable_mets": pick(
        "mets_",
    ),

    "meals": meals_logged,

    "meals_consumed":
        meals_consumed,

    "time": [
        "hour_sin",
        "hour_cos",
    ],

    "static": static_columns,
}


meta = {

    "groups": groups,

    "categorical": [
        "last_meal_type",
    ],

    "events": {
        key: {
            "threshold": value[0],
            "direction": value[1],
        }
        for key, value
        in EVENTS.items()
    },

    "risk_horizons":
        RISK_HORIZONS,

    "future_horizons":
        FUTURE_HORIZONS,

    "target_columns":
        pick("target_"),

    "label_columns":
        pick(*event_prefixes),

    "small_policy":
        SMALL_POLICY,

    "excluded_subjects":
        sorted(
            EXCLUDE_SUBJECTS
        ),

    "merge_intensity":
        MERGE_INTENSITY,

    "amount_rule": (
        "values >100 divided by 10; "
        "values <=100 kept as percentage; "
        "stored as 0-1 fraction; "
        "codes 1-4 handled by "
        "small_policy"
    ),

    "missing_amount_policy": (
        "unknown amount assumes the "
        "full meal was eaten "
        "(amount_known = 0)"
    ),

    "macro_caps": {
        k: float(v)
        for k, v in CAPS.items()
    },
}


(
    OUT / "columns.json"
).write_text(
    json.dumps(
        meta,
        indent=2,
    )
)

data.to_parquet(
    OUT / "glucose_15min.parquet",
    index=False,
)

meals_all.to_parquet(
    OUT / "meals_clean.parquet",
    index=False,
)


info_df = pd.DataFrame(
    infos
)


print(
    "\n=== PARTICIPANTS ==="
)

print(
    info_df.to_string(
        index=False
    )
)

print(
    "\nRows:",
    len(data),
    "| Subjects:",
    data[
        "subject"
    ].nunique(),
    "| Meals:",
    len(meals_all),
)

print(
    "Rows per fold:",
    data[
        "fold"
    ]
    .value_counts()
    .sort_index()
    .to_dict()
)


print(
    "\n=== LIBRE vs DEXCOM OFFSET ==="
)

print(
    "Spearman("
    "libre_minus_dexcom, "
    "low70_events):",
    round(
        spearman(
            info_df[
                "libre_minus_dexcom"
            ],
            info_df[
                "low70_events"
            ],
        ),
        3,
    ),
)

print(
    info_df
    .sort_values(
        "libre_minus_dexcom"
    )
    .head(8)[
        [
            "subject",
            "libre_minus_dexcom",
            "low70_events",
            "high180_events",
        ]
    ]
    .to_string(
        index=False
    )
)


print(
    "\n=== CONSUMED NUTRIENT SUMMARY ==="
)

print(
    meals_all[
        [
            f"{lc}_eaten"
            for lc in LCS
        ]
    ]
    .describe()
    .T
    .round(2)
    .to_string()
)

print(
    "amount known for",
    round(
        100
        * meals_all[
            "amount_known"
        ].mean(),
        1,
    ),
    "% of meals",
)


print(
    "\n=== MEAL RESPONSE BY AMOUNT RULE ==="
)

print(
    meals_all
    .groupby(
        "amount_rule"
    )
    .agg(
        meals=(
            "rise_2h",
            "size",
        ),
        with_response=(
            "rise_2h",
            "count",
        ),
        median_carbs_full=(
            "carbs_full",
            "median",
        ),
        median_rise=(
            "rise_2h",
            "median",
        ),
    )
    .round(1)
    .to_string()
)


response = (
    meals_all
    .dropna(
        subset=["rise_2h"]
    )
    .copy()
)

response[
    "carbs_literal"
] = (
    response[
        "carbs_full"
    ]
    * response[
        "fraction_literal"
    ]
)

response[
    "carbs_assume_full"
] = (
    response[
        "carbs_full"
    ]
    * response[
        "fraction_assume_full"
    ]
)


print(
    "\nSpearman correlation "
    "of glucose rise with carbs:"
)

rows = []

for column, label in [
    (
        "carbs_full",
        "full meal carbs, "
        "no scaling",
    ),
    (
        "carbs_literal",
        "consumed, codes "
        "1-4 as percents",
    ),
    (
        "carbs_assume_full",
        "consumed, codes "
        "1-4 assumed full",
    ),
]:

    per_subject = [
        spearman(
            group[column],
            group["rise_2h"],
        )
        for _, group
        in response.groupby(
            "subject"
        )
        if len(group) >= 15
    ]

    rows.append({
        "carbs version": label,
        "pooled": round(
            spearman(
                response[column],
                response["rise_2h"],
            ),
            3,
        ),
        "mean_per_subject":
            round(
                float(
                    np.nanmean(
                        per_subject
                    )
                ),
                3,
            ),
        "subjects":
            len(per_subject),
    })


print(
    pd.DataFrame(
        rows
    ).to_string(
        index=False
    )
)


print(
    "\n=== TIME TO EVENT ==="
)

rows = []

for name in EVENTS:

    usable = data[
        data[
            f"{name}_usable"
        ] == 1
    ]

    events = usable[
        usable[
            f"{name}_event"
        ] == 1
    ]

    rows.append({
        "event": name,
        "at_risk_rows":
            len(usable),
        "events":
            len(events),
        "event_pct":
            round(
                100
                * len(events)
                / max(
                    len(usable),
                    1,
                ),
                1,
            ),
        "median_tte_min":
            events[
                f"{name}_tte"
            ].median(),
        "subjects_with_event":
            events[
                "subject"
            ].nunique(),
    })


print(
    pd.DataFrame(
        rows
    ).to_string(
        index=False
    )
)


print(
    "\n=== OBSERVED P(event within h minutes) ==="
)

ci = {}

for name in EVENTS:

    usable = data[
        data[
            f"{name}_usable"
        ] == 1
    ]

    ci[name] = [
        round(
            usable[
                f"{name}_within_{h}"
            ].mean(),
            3,
        )
        for h
        in RISK_HORIZONS
    ]


print(
    pd.DataFrame(
        ci,
        index=[
            f"{h} min"
            for h
            in RISK_HORIZONS
        ],
    )
    .T
    .to_string()
)


print(
    "\n=== TARGET COVERAGE ==="
)

print(
    {
        h: int(
            data[
                f"target_{h}"
            ].notna().sum()
        )
        for h in [
            30,
            60,
            120,
            240,
            360,
        ]
    }
)


print(
    "\n=== MISSING % ==="
)

important = [
    "hr_mean_15",
    "mets_mean_15",
    "act_level_mean_15",
    "act_active_frac_60",
    "activity_calories_60",
    "last_carbs_eaten",
    "hba1c",
    "homa_ir",
    "target_60",
]

print(
    (
        100
        * data[
            important
        ]
        .isna()
        .mean()
    )
    .round(2)
    .to_string()
)


print(
    "\nSaved:",
    OUT / "glucose_15min.parquet",
    data.shape,
)

print(
    "Saved:",
    OUT / "meals_clean.parquet",
    meals_all.shape,
)

print(
    "Saved:",
    OUT / "columns.json",
)