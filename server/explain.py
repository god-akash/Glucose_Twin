import json
import os
import re

import requests

LABELS = {
    "high180": "high glucose (above 180 mg/dL)",
    "high140": "elevated glucose (above 140 mg/dL)",
    "low70": "low glucose (below 70 mg/dL)",
}

BANNED = (
    "insulin",
    "medication",
    "medicine",
    "metformin",
    "dose",
    "dosage",
    "prescri",
    "treat",
    "recommend",
    "you should",
    "should eat",
    "should take",
    "diet",
    "exercise",
)

SYSTEM = (
    "You write a short briefing for a clinician about a research prototype "
    "that estimates glucose-event risk. Use only the facts in the JSON. "
    "Never add numbers, causes, diagnoses, or any treatment, medication, "
    "insulin, diet or exercise advice, and never tell anyone what to do. "
    "Do not guess missing facts. State that the figures are model estimates. "
    "Cover, in this order: the current glucose and its trend; the focus "
    "event's risk and how soon it could be reached; the main factors from "
    "drivers (they describe model inputs, not proven causes); the last meal "
    "and heart rate if present; and any other event that is in_event or at "
    "watch or alert level. If an event has status in_event, say glucose is "
    "already past its threshold and no forecast is shown for it. If "
    "experimental_model is true for an event, call that model experimental. "
    "If what_if is present, explain how the 2-hour estimate changes if that "
    "meal were logged now, as a model estimate only. Write 5 to 7 plain "
    "sentences, under 150 words, with no lists, headings or markdown."
)


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


def _r(x):
    try:
        return None if x is None or x != x else round(float(x))
    except (TypeError, ValueError):
        return None


def trend_label(feats):
    change = feats.get("glucose_change_15")

    if change is None or change != change:
        return None

    rate = change / 15

    return (
        "rising rapidly"
        if rate > 2
        else (
            "rising"
            if rate >= 1
            else (
                "falling rapidly"
                if rate < -2
                else "falling" if rate <= -1 else "steady"
            )
        )
    )


def activity_label(level):
    if level is None:
        return None

    return (
        "mostly resting"
        if level < 0.5
        else "light to moderate activity" if level < 1.5 else "vigorous activity"
    )


def _reach(value):
    if value is None:
        return "not within 6 hours"

    return "30 minutes or sooner" if value <= 30 else int(value)


def build_facts(entry, feats, tasks, focus, drivers, alerts, what_if=None):
    signals = entry.get("signals") or {}

    facts = {
        "time": entry["timestamp"][11:16],
        "glucose_mg_dl": _r(entry["glucose"]),
        "trend": trend_label(feats),
        "focus_event": LABELS.get(focus, focus),
        "data_note": "model trained on a public 44-person research dataset",
    }

    for key, output_name in (
        ("glucose_change_30", "glucose_change_30_min"),
        ("glucose_change_60", "glucose_change_60_min"),
    ):
        value = _r(feats.get(key))

        if value is not None:
            facts[output_name] = value

    if signals.get("hr_bpm") is not None:
        facts["heart_rate_bpm"] = signals["hr_bpm"]

    activity = activity_label(signals.get("activity_level"))

    if activity:
        facts["activity"] = activity

    events = []

    for name, task in tasks.items():
        event = {
            "event": LABELS.get(name, name),
            "status": task.get("status"),
            "experimental_model": bool(task.get("exploratory")),
        }

        if task.get("status") == "ok":
            risk = task["risk"]
            reach = task.get("time_to_risk_min") or {}

            event.update(
                {
                    "alert_level": task.get("level"),
                    "risk_percent_2h": round(risk["120"] * 100),
                    "risk_percent_6h": round(risk["360"] * 100),
                    "minutes_to_30_percent": _reach(reach.get("30")),
                    "minutes_to_50_percent": _reach(reach.get("50")),
                }
            )

        events.append(event)

    facts["events"] = events

    if tasks.get(focus, {}).get("status") == "ok":
        facts["alert_rule"] = (
            f"watch at {round(alerts['sensitive'] * 100)}% and alert at "
            f"{round(alerts['balanced'] * 100)}% chance within 2 hours"
        )
        facts["drivers"] = drivers

    since = feats.get("minutes_since_meal")

    if (
        feats.get("last_meal_type") not in (None, "none")
        and since is not None
        and since < 480
    ):
        facts["last_meal"] = {
            "type": feats["last_meal_type"],
            "minutes_ago": _r(since),
            "carbs_g": _r(feats.get("last_carbs_full")),
        }

    if what_if:
        facts["what_if"] = what_if

    return facts


def template_text(facts):
    text = f"At {facts['time']} glucose is {facts['glucose_mg_dl']} mg/dL"

    if facts.get("trend"):
        text += f" and {facts['trend']}"

    if facts.get("glucose_change_60_min") is not None:
        text += f" ({facts['glucose_change_60_min']:+d} mg/dL " "over the last hour)"

    parts = [text + "."]

    if facts.get("heart_rate_bpm") is not None:
        line = f"Heart rate is about {facts['heart_rate_bpm']} bpm"

        if facts.get("activity"):
            line += f" with {facts['activity']}"

        parts.append(line + ".")

    for event in facts["events"]:
        if event["status"] == "in_event":
            parts.append(
                f"For {event['event']}, glucose is already past the "
                "threshold, so no forecast is shown."
            )

        elif event["status"] == "ok":
            line = (
                f"For {event['event']}, the model estimates a "
                f"{event['risk_percent_2h']}% chance within 2 hours "
                f"and {event['risk_percent_6h']}% within 6 hours "
                f"(level: {event['alert_level']})"
            )

            reach = event.get("minutes_to_50_percent")

            if reach is not None:
                if isinstance(reach, int):
                    line += f"; the chance reaches 50% in about {reach} minutes"
                else:
                    line += f"; the chance reaches 50% {reach}"

            if event.get("experimental_model"):
                line += " (experimental model)"

            parts.append(line + ".")

    if facts.get("drivers"):
        items = [
            f"{driver['factor']} ({driver['effect']}, {driver['strength']})"
            for driver in facts["drivers"]
        ]

        parts.append(
            f"For {facts['focus_event']}, the main factors are "
            + "; ".join(items)
            + "."
        )

    meal = facts.get("last_meal")

    if meal and meal.get("minutes_ago") is not None:
        line = (
            f"The last logged meal was a {meal['type']} "
            f"{meal['minutes_ago']} minutes ago"
        )

        if meal.get("carbs_g") is not None:
            line += f" with about {meal['carbs_g']} g of carbohydrate"

        parts.append(line + ".")

    what_if = facts.get("what_if")

    if what_if:
        parts.append(
            f"If a {what_if['meal_type']} with about "
            f"{what_if['carbs_g']} g of carbohydrate were logged now, "
            f"the 2-hour chance for {what_if['event']} would move from "
            f"{what_if['risk_percent_2h_now']}% to "
            f"{what_if['risk_percent_2h_after_meal']}%."
        )

    parts.append("These are model estimates, not a diagnosis.")

    return " ".join(parts)


# Hosted AI provider using an OpenAI-compatible chat API.
def _post(base_url, api_key, payload):
    return requests.post(
        f"{base_url}/chat/completions",
        timeout=45,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
    )


def llm_text(facts):
    if os.environ.get("LLM_PROVIDER", "").lower() == "none":
        return None, "language model disabled", None

    api_key = os.environ.get("LLM_API_KEY", "").strip()

    base_url = os.environ.get(
        "LLM_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ).rstrip("/")

    model = os.environ.get("LLM_MODEL", "gemini-2.5-flash")

    if not api_key:
        return None, "LLM_API_KEY is not set", model

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(facts)},
        ],
    }

    try:
        response = _post(
            base_url,
            api_key,
            {
                **payload,
                "temperature": 0.2,
                "max_tokens": 1000,
            },
        )

        # Retry without optional generation parameters if unsupported.
        if response.status_code == 400:
            response = _post(base_url, api_key, payload)

        if response.status_code in (401, 403):
            return None, "the API key was rejected", model

        if response.status_code == 404:
            return None, f"model or address not found ({model})", model

        if response.status_code == 429:
            return None, "rate limit reached; try again in a minute", model

        response.raise_for_status()

        answer = (response.json()["choices"][0]["message"].get("content") or "").strip()

        if not answer:
            return None, "empty reply", model

        return answer, None, model

    except requests.exceptions.Timeout:
        return None, "the AI service timed out", model

    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", model


def _numbers(value, output):
    if isinstance(value, bool) or value is None:
        return

    if isinstance(value, (int, float)):
        output.add(round(abs(float(value))))

    elif isinstance(value, str):
        output.update(
            round(float(match)) for match in re.findall(r"\d+(?:\.\d+)?", value)
        )

    elif isinstance(value, dict):
        for key, item in value.items():
            _numbers(str(key), output)
            _numbers(item, output)

    elif isinstance(value, list):
        for item in value:
            _numbers(item, output)


def numbers_ok(text, facts):
    allowed = {0, 1, 2, 3, 4, 5, 6, 24}
    _numbers(facts, allowed)

    for match in re.findall(r"\d+(?:\.\d+)?", text):
        number = float(match)

        if not any(abs(number - allowed_number) <= 1 for allowed_number in allowed):
            return False

    return True


def explain(facts, use_llm=True):
    fallback = template_text(facts)

    if not use_llm:
        return {
            "text": fallback,
            "source": "template",
            "model": None,
        }

    answer, error, model = llm_text(facts)

    if answer:
        answer = re.sub(r"[*#`_]", "", answer).strip()
        lower_answer = answer.lower()

        if len(answer) > 1100:
            error = "the reply was too long"

        elif any(word in lower_answer for word in BANNED):
            error = "the reply contained advice-like wording"

        elif not numbers_ok(answer, facts):
            error = "the reply contained numbers not in the facts"

        else:
            return {
                "text": answer,
                "source": "llm",
                "model": f"gemini:{model}",
            }

    return {
        "text": fallback,
        "source": "template",
        "model": None,
        "llm_fallback_reason": error or "no reply",
    }
