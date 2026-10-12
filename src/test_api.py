import math
import os
import sys

import requests


BASE_URL = os.getenv(
    "GLUCOSE_TWIN_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

PATIENT_ID = "cgm-036"

TASKS = ("high180", "high140", "low70")
HORIZONS = ("30", "60", "90", "120", "180", "240", "300", "360")

MEAL = {
    "meal_type": "lunch",
    "calories": 700,
    "carbs": 90,
    "protein": 25,
    "fat": 20,
    "fiber": 6,
}

TIMEOUT = 20


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def get_json(response, description):
    check(
        200 <= response.status_code < 300,
        (
            f"{description} failed: HTTP {response.status_code}\n"
            f"{response.text[:1000]}"
        ),
    )

    try:
        return response.json()
    except ValueError as exc:
        raise AssertionError(
            f"{description} did not return valid JSON."
        ) from exc


def get_latest():
    response = requests.get(
        f"{BASE_URL}/patients/{PATIENT_ID}/latest",
        timeout=TIMEOUT,
    )
    return get_json(response, "Latest prediction request")


def get_tasks(data, description):
    check(
        isinstance(data, dict),
        f"{description}: response must be a JSON object.",
    )

    # /latest nests tasks under "tasks".
    # /whatif returns tasks directly inside baseline/with_meal.
    tasks = data.get("tasks")

    if tasks is None and all(name in data for name in TASKS):
        tasks = data

    check(
        isinstance(tasks, dict),
        f"{description}: expected a task object or nested 'tasks' object.",
    )

    missing = set(TASKS) - set(tasks)

    check(
        not missing,
        f"{description}: missing tasks: {sorted(missing)}",
    )

    return tasks

def validate_risks(tasks, description):
    for task_name in TASKS:
        task = tasks[task_name]

        check(
            isinstance(task, dict),
            f"{description}: {task_name} must be an object.",
        )

        # An already-occurring event may be represented separately.
        if task.get("status") == "in_event":
            continue

        risks = task.get("risk")

        check(
            isinstance(risks, dict),
            f"{description}: {task_name} is missing its risk map.",
        )

        missing_horizons = set(HORIZONS) - set(risks)

        check(
            not missing_horizons,
            (
                f"{description}: {task_name} is missing horizons "
                f"{sorted(missing_horizons)}."
            ),
        )

        values = []

        for horizon in HORIZONS:
            value = risks[horizon]

            check(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value),
                (
                    f"{description}: {task_name} risk at "
                    f"{horizon} minutes is not finite."
                ),
            )

            check(
                0.0 <= value <= 1.0,
                (
                    f"{description}: {task_name} risk at "
                    f"{horizon} minutes is outside [0, 1]."
                ),
            )

            values.append(float(value))

        for earlier, later in zip(values, values[1:]):
            check(
                later + 1e-9 >= earlier,
                (
                    f"{description}: {task_name} risk curve "
                    "decreases across horizons."
                ),
            )


def assert_same_risks(first, second, description):
    for task_name in TASKS:
        first_risk = first[task_name].get("risk")
        second_risk = second[task_name].get("risk")

        check(
            isinstance(first_risk, dict)
            and isinstance(second_risk, dict),
            f"{description}: risk map missing for {task_name}.",
        )

        check(
            set(first_risk) == set(second_risk),
            f"{description}: horizons changed for {task_name}.",
        )

        for horizon in first_risk:
            a = first_risk[horizon]
            b = second_risk[horizon]

            check(
                math.isclose(
                    float(a),
                    float(b),
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ),
                (
                    f"{description}: {task_name} risk changed "
                    f"at {horizon} minutes: {a} vs {b}."
                ),
            )


def main():
    print(f"API: {BASE_URL}")
    print(f"Patient: {PATIENT_ID}")
    print("-" * 55)

    # Test 1: Initial latest prediction
    before = get_latest()

    check(
        before.get("predicted") is True,
        "Latest endpoint did not report predicted=true.",
    )

    check(
        isinstance(before.get("glucose"), (int, float)),
        "Latest endpoint did not return numerical glucose.",
    )

    before_tasks = get_tasks(before, "Latest prediction")
    validate_risks(before_tasks, "Latest prediction")

    print("[PASS] Latest endpoint returns all task predictions.")

    # Test 2: Meal what-if response
    response = requests.post(
        f"{BASE_URL}/whatif",
        json={
            "patient_id": PATIENT_ID,
            "meal": MEAL,
        },
        timeout=TIMEOUT,
    )

    whatif = get_json(response, "Meal what-if request")

    check(
        "baseline" in whatif and "with_meal" in whatif,
        "What-if response must contain baseline and with_meal.",
    )

    baseline = get_tasks(
        whatif["baseline"],
        "What-if baseline",
    )
    with_meal = get_tasks(
        whatif["with_meal"],
        "What-if with_meal",
    )

    validate_risks(baseline, "What-if baseline")
    validate_risks(with_meal, "What-if with_meal")

    print("[PASS] What-if returns valid numerical risk estimates.")

    # Test 3: What-if baseline agrees with latest predictions
    assert_same_risks(
        before_tasks,
        baseline,
        "Latest versus what-if baseline",
    )

    print("[PASS] What-if baseline matches the latest predictions.")

    # Test 4: Hypothetical meal must not change stored state
    after = get_latest()
    after_tasks = get_tasks(after, "Latest prediction after what-if")

    assert_same_risks(
        before_tasks,
        after_tasks,
        "Before versus after what-if",
    )

    check(
        before.get("timestamp") == after.get("timestamp"),
        "Latest timestamp changed after the what-if request.",
    )

    check(
        math.isclose(
            float(before["glucose"]),
            float(after["glucose"]),
            rel_tol=0,
            abs_tol=1e-9,
        ),
        "Latest glucose changed after the what-if request.",
    )

    print("[PASS] What-if did not change latest glucose or risks.")

    # Test 5: Invalid requests should return a client error,
    # rather than succeeding or crashing with HTTP 5xx.
    invalid_response = requests.post(
        f"{BASE_URL}/whatif",
        json={},
        timeout=TIMEOUT,
    )

    check(
        400 <= invalid_response.status_code < 500,
        (
            "Empty what-if payload should be rejected with HTTP "
            f"4xx, got HTTP {invalid_response.status_code}.\n"
            f"{invalid_response.text[:1000]}"
        ),
    )

    print(
        "[PASS] Empty what-if payload rejected with "
        f"HTTP {invalid_response.status_code}."
    )

    print("-" * 55)
    print("ALL API TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"\nAPI CONNECTION ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except AssertionError as exc:
        print(f"\nTEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)