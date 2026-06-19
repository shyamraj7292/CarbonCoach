"""
Deterministic emissions calculation engine.

The agent (LLM) maps natural language to (category, activity, quantity, unit);
this module does the actual arithmetic against curated emission factors so
CO2e numbers are never hallucinated.
"""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "emission_factors.json")

with open(_DATA_PATH, "r", encoding="utf-8") as f:
    _FACTORS = json.load(f)


class UnknownActivityError(ValueError):
    pass


def list_activities() -> dict:
    """Return all known categories/activities with their labels and units."""
    return {
        category: {
            key: {"label": entry["label"], "unit": entry["unit"]}
            for key, entry in activities.items()
        }
        for category, activities in _FACTORS.items()
        if category not in ("_meta", "benchmarks")
    }


def calculate_emissions(category: str, activity: str, quantity: float) -> dict:
    """
    Calculate kg CO2e for a given activity and quantity.

    Args:
        category: top-level group, e.g. "transport", "food", "energy", "shopping", "waste"
        activity: specific activity key, e.g. "car_petrol_medium", "beef"
        quantity: amount in the activity's native unit (see list_activities)

    Returns:
        dict with category, activity, label, quantity, unit, factor, co2e_kg
    """
    if category not in _FACTORS or category in ("_meta", "benchmarks"):
        raise UnknownActivityError(f"Unknown category: {category}")

    activities = _FACTORS[category]
    if activity not in activities:
        raise UnknownActivityError(f"Unknown activity '{activity}' in category '{category}'")

    entry = activities[activity]
    factor = entry["factor"]
    co2e_kg = round(factor * quantity, 4)

    return {
        "category": category,
        "activity": activity,
        "label": entry["label"],
        "quantity": quantity,
        "unit": entry["unit"],
        "factor_kg_co2e_per_unit": factor,
        "co2e_kg": co2e_kg,
    }


def get_benchmarks() -> dict:
    return _FACTORS["benchmarks"]


def compare_to_average(annual_kg: float, country: str = "global") -> dict:
    """Compare an annualized footprint to country/global averages and the Paris target."""
    benchmarks = _FACTORS["benchmarks"]
    country_key = country.lower()
    country_avg = benchmarks["country_averages_annual_kg"].get(
        country_key, benchmarks["global_average_annual_kg"]
    )
    target = benchmarks["paris_target_2030_annual_kg"]

    return {
        "annual_kg": round(annual_kg, 2),
        "country": country_key,
        "country_average_annual_kg": country_avg,
        "global_average_annual_kg": benchmarks["global_average_annual_kg"],
        "paris_target_2030_annual_kg": target,
        "vs_country_average_pct": round((annual_kg / country_avg - 1) * 100, 1) if country_avg else None,
        "vs_paris_target_pct": round((annual_kg / target - 1) * 100, 1) if target else None,
    }
