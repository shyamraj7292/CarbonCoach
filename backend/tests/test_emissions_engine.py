import pytest

from services.emissions_engine import (
    calculate_emissions,
    compare_to_average,
    list_activities,
    UnknownActivityError,
)


def test_calculate_emissions_basic():
    result = calculate_emissions("transport", "car_petrol_medium", 15)
    assert result["co2e_kg"] == pytest.approx(2.88)
    assert result["unit"] == "km"
    assert result["category"] == "transport"


def test_calculate_emissions_food():
    result = calculate_emissions("food", "beef", 2)
    assert result["co2e_kg"] == pytest.approx(14.4)


def test_zero_factor_activity():
    result = calculate_emissions("transport", "bicycle", 10)
    assert result["co2e_kg"] == 0


def test_unknown_category_raises():
    with pytest.raises(UnknownActivityError):
        calculate_emissions("not_a_category", "x", 1)


def test_unknown_activity_raises():
    with pytest.raises(UnknownActivityError):
        calculate_emissions("transport", "rocket", 1)


def test_list_activities_excludes_meta():
    activities = list_activities()
    assert "_meta" not in activities
    assert "benchmarks" not in activities
    assert "transport" in activities
    assert "car_petrol_medium" in activities["transport"]


def test_compare_to_average_global():
    result = compare_to_average(4700, "global")
    assert result["vs_country_average_pct"] == 0.0
    assert result["vs_paris_target_pct"] == pytest.approx(88.0)


def test_compare_to_average_unknown_country_falls_back_to_global():
    result = compare_to_average(4700, "atlantis")
    assert result["country_average_annual_kg"] == result["global_average_annual_kg"]
