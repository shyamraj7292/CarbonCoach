"""
Tool implementations the agent can call. Each tool returns plain JSON-serializable
dicts. Numbers always come from emissions_engine — the agent never invents CO2e values.
"""

from datetime import datetime, timedelta, timezone

from services.emissions_engine import (
    calculate_emissions,
    compare_to_average,
    list_activities,
    UnknownActivityError,
)
from services.storage_service import storage

PERIOD_DAYS = {"today": 1, "week": 7, "month": 30, "year": 365}

# (category, activity) -> alternative activity key in the same category,
# used by suggest_swaps to recommend lower-carbon substitutes.
SWAP_RULES = {
    ("food", "beef"): ("chicken", "Swap beef for chicken"),
    ("food", "lamb"): ("chicken", "Swap lamb for chicken"),
    ("food", "dairy_meal"): ("vegetarian", "Swap a dairy-heavy meal for a vegetarian one"),
    ("food", "pork"): ("chicken", "Swap pork for chicken"),
    ("food", "chicken"): ("vegetarian", "Swap chicken for a vegetarian meal"),
    ("transport", "car_petrol_large"): ("car_petrol_small", "Downsize from a large to a small petrol car"),
    ("transport", "car_petrol_medium"): ("bus", "Take the bus instead of driving"),
    ("transport", "car_petrol_small"): ("bicycle", "Cycle instead of driving short trips"),
    ("transport", "taxi_rideshare"): ("subway", "Take the subway/metro instead of a taxi"),
    ("transport", "flight_short_haul"): ("train", "Take the train instead of a short-haul flight"),
    ("transport", "car_diesel_medium"): ("train", "Take the train instead of driving"),
    ("energy", "ac_hour"): ("ac_hour", "Cut AC usage by ~30% (e.g. raise the thermostat 2°C)"),
    ("energy", "heating_hour"): ("heating_hour", "Cut heater usage by ~30% (e.g. lower the thermostat 2°C)"),
}

# Activities where the "swap" is a usage reduction rather than a substitute activity.
REDUCTION_RULES = {("energy", "ac_hour"), ("energy", "heating_hour")}
REDUCTION_FACTOR = 0.3


def _period_start(period: str) -> str:
    days = PERIOD_DAYS.get(period, 7)
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def tool_calculate_emissions(category: str, activity: str, quantity: float) -> dict:
    try:
        return calculate_emissions(category, activity, quantity)
    except UnknownActivityError as e:
        return {"error": str(e), "available_activities": list_activities()}


def tool_log_activity(user_id: str, category: str, activity: str, quantity: float, note: str = "") -> dict:
    try:
        result = calculate_emissions(category, activity, quantity)
    except UnknownActivityError as e:
        return {"error": str(e), "available_activities": list_activities()}

    record = storage.add_activity(user_id, {**result, "note": note})
    return record


def tool_get_history(user_id: str, period: str = "week") -> dict:
    since = _period_start(period)
    activities = storage.get_activities(user_id, since=since)

    total = 0.0
    by_category: dict[str, float] = {}
    by_activity: dict[str, dict] = {}

    for a in activities:
        total += a["co2e_kg"]
        by_category[a["category"]] = by_category.get(a["category"], 0) + a["co2e_kg"]

        key = f"{a['category']}:{a['activity']}"
        if key not in by_activity:
            by_activity[key] = {
                "category": a["category"],
                "activity": a["activity"],
                "label": a["label"],
                "unit": a["unit"],
                "quantity": 0.0,
                "co2e_kg": 0.0,
            }
        by_activity[key]["quantity"] += a["quantity"]
        by_activity[key]["co2e_kg"] += a["co2e_kg"]

    return {
        "period": period,
        "total_co2e_kg": round(total, 2),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "by_activity": {k: {**v, "quantity": round(v["quantity"], 2), "co2e_kg": round(v["co2e_kg"], 2)}
                         for k, v in by_activity.items()},
        "activity_count": len(activities),
        "activities": activities,
    }


def tool_compare_to_average(user_id: str, country: str | None = None) -> dict:
    user = storage.get_user(user_id)
    country = country or user.get("country", "global")
    history = tool_get_history(user_id, "week")
    annualized = history["total_co2e_kg"] / 7 * 365
    return compare_to_average(annualized, country)


def tool_suggest_swaps(user_id: str, top_n: int = 3) -> dict:
    history = tool_get_history(user_id, "month")
    suggestions = []

    for key, entry in history["by_activity"].items():
        cat, act = entry["category"], entry["activity"]
        rule = SWAP_RULES.get((cat, act))
        if not rule:
            continue
        alt_activity, description = rule

        if (cat, act) in REDUCTION_RULES:
            savings_kg = entry["co2e_kg"] * REDUCTION_FACTOR
            suggestions.append({
                "current_activity": entry["label"],
                "suggestion": description,
                "monthly_savings_kg_co2e": round(savings_kg, 2),
            })
            continue

        try:
            current = calculate_emissions(cat, act, entry["quantity"])
            alt = calculate_emissions(cat, alt_activity, entry["quantity"])
        except UnknownActivityError:
            continue

        savings_kg = current["co2e_kg"] - alt["co2e_kg"]
        if savings_kg <= 0:
            continue

        suggestions.append({
            "current_activity": entry["label"],
            "alternative_activity": alt["label"],
            "suggestion": description,
            "monthly_savings_kg_co2e": round(savings_kg, 2),
        })

    suggestions.sort(key=lambda s: s["monthly_savings_kg_co2e"], reverse=True)
    return {"suggestions": suggestions[:top_n]}


def tool_list_activities() -> dict:
    return list_activities()
