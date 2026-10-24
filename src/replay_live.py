import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed" / "replay"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replay Glucose Twin data as minute-by-minute ingestion."
    )
    parser.add_argument("subject", type=int)
    parser.add_argument("--hours", type=float, default=1)
    parser.add_argument(
        "--seconds-per-minute",
        type=float,
        default=1.0,
        help="Wall-clock seconds per simulated data minute. Use 60 for real time.",
    )
    parser.add_argument(
        "--api",
        default="http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=1,
        help="Print a status line every N simulated minutes.",
    )
    return parser.parse_args()


def clean_value(value):
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    return value


def timestamp_string(value):
    return pd.Timestamp(value).isoformat()


def event_to_payload(group):
    wearable = []
    glucose = []
    meals = []

    if group is None or group.empty:
        return {
            "wearable": wearable,
            "glucose": glucose,
            "meals": meals,
            "do_predict": True,
        }

    for row in group.itertuples(index=False):
        ts = timestamp_string(row.timestamp)

        if row.kind == "wearable":
            wearable.append({
                "timestamp": ts,
                "hr": clean_value(row.hr),
                "act_level": clean_value(row.act_level),
                "activity_calories": clean_value(
                    row.activity_calories
                ),
            })

        elif row.kind == "glucose":
            value = clean_value(row.value)

            if value is not None:
                glucose.append({
                    "timestamp": ts,
                    "value": float(value),
                })

        elif row.kind == "meal":
            meals.append({
                "timestamp": ts,
                "meal_type": (
                    "snack"
                    if row.meal_type is None
                    or pd.isna(row.meal_type)
                    else str(row.meal_type)
                ),
                "calories": clean_value(row.calories),
                "carbs": clean_value(row.carbs),
                "protein": clean_value(row.protein),
                "fat": clean_value(row.fat),
                "fiber": clean_value(row.fiber),
            })

        else:
            raise ValueError(
                f"Unknown event kind: {row.kind}"
            )

    return {
        "wearable": wearable,
        "glucose": glucose,
        "meals": meals,
        "do_predict": True,
    }


def main():
    args = parse_args()

    if args.hours <= 0:
        raise SystemExit("--hours must be positive.")

    if args.seconds_per_minute <= 0:
        raise SystemExit("--seconds-per-minute must be positive.")

    if args.log_every < 1:
        raise SystemExit("--log-every must be at least 1.")

    subject = args.subject
    patient_id = f"cgm-{subject:03d}"
    api = args.api.rstrip("/")

    event_path = DATA_DIR / f"events_{subject:03d}.parquet"

    if not event_path.exists():
        raise FileNotFoundError(
            f"Replay events not found: {event_path}\n"
            f"Generate them with src/make_replay.py first."
        )

    events = pd.read_parquet(event_path)

    if events.empty:
        raise ValueError(f"No events found in {event_path}")

    required = {
        "kind",
        "timestamp",
        "hr",
        "act_level",
        "activity_calories",
        "value",
        "meal_type",
        "calories",
        "carbs",
        "protein",
        "fat",
        "fiber",
    }

    missing = required - set(events.columns)

    if missing:
        raise ValueError(
            f"Replay file is missing columns: {sorted(missing)}"
        )

    events["timestamp"] = pd.to_datetime(
        events["timestamp"],
        errors="raise",
    )

    events = events.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    events["minute_bucket"] = events["timestamp"].dt.floor("min")

    first_minute = events["minute_bucket"].min()
    end_time = first_minute + pd.Timedelta(hours=args.hours)

    events = events[
        events["minute_bucket"] < end_time
    ].copy()

    if events.empty:
        raise ValueError("No events are available in this time window.")

    grouped = {
        pd.Timestamp(minute): group.drop(
            columns=["minute_bucket"]
        )
        for minute, group in events.groupby(
            "minute_bucket",
            sort=True,
        )
    }

    last_minute = events["minute_bucket"].max()

    
    minutes = pd.date_range(
        start=first_minute,
        end=last_minute,
        freq="min",
    )

    reset_payload = {
        "patient_id": patient_id,
        "mode": "cv",
        "subject": subject,
    }

    print(f"API: {api}")
    print(f"Patient: {patient_id}")
    print(f"Simulated minutes: {len(minutes)}")
    print(f"Seconds per simulated minute: {args.seconds_per_minute}")
    print("Resetting patient state...")

    session = requests.Session()

    try:
        response = session.post(
            f"{api}/reset",
            json=reset_payload,
            timeout=30,
        )

        if not response.ok:
            raise RuntimeError(
                f"Reset failed: HTTP {response.status_code}\n"
                f"{response.text[:1000]}"
            )

        print("Reset:", response.json())

        start_wall = time.monotonic()
        successful = 0

        for index, minute in enumerate(minutes):
            # Pace each batch according to simulation time.
            target_elapsed = index * args.seconds_per_minute
            remaining = target_elapsed - (
                time.monotonic() - start_wall
            )

            if remaining > 0:
                time.sleep(remaining)

            minute = pd.Timestamp(minute)
            group = grouped.get(minute)

            payload = event_to_payload(group)

            response = session.post(
                f"{api}/ingest",
                json={
                    "patient_id": patient_id,
                    **payload,
                },
                timeout=30,
            )

            if not response.ok:
                raise RuntimeError(
                    f"Ingestion failed at {minute.isoformat()}: "
                    f"HTTP {response.status_code}\n"
                    f"{response.text[:1000]}"
                )

            result = response.json()
            successful += 1

            if index % args.log_every == 0 or index == len(minutes) - 1:
                latest = result.get("latest") or {}

                task = latest.get("tasks", {}).get(
                    "high180", {}
                )

                risk = task.get("risk", {}).get("120")
                level = task.get("level", task.get("status", "pending"))

                glucose_value = latest.get("glucose")
                glucose_text = (
                    f"{glucose_value:.1f} mg/dL"
                    if isinstance(glucose_value, (int, float))
                    else "no reading yet"
                )

                risk_text = (
                    f"{risk * 100:.1f}%"
                    if isinstance(risk, (int, float))
                    else "n/a"
                )

                counts = (
                    f"wearable={len(payload['wearable'])}, "
                    f"glucose={len(payload['glucose'])}, "
                    f"meals={len(payload['meals'])}"
                )

                print(
                    f"[{index + 1}/{len(minutes)}] "
                    f"{minute.isoformat()} | "
                    f"{counts} | "
                    f"latest={glucose_text} | "
                    f"high180@120m={risk_text} ({level})"
                )

        print("\nReplay finished.")
        print(f"Minute batches successfully sent: {successful}")
        print(f"Patient: {patient_id}")

    finally:
        session.close()


if __name__ == "__main__":
    main()