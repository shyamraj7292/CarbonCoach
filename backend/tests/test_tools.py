import json
import os

import pytest

from services import storage_service, tools


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    store_path = tmp_path / "store.json"
    store_path.write_text(json.dumps({"users": {}, "activities": []}))
    test_storage = storage_service.LocalJsonStorage(str(store_path))
    monkeypatch.setattr(storage_service, "storage", test_storage)
    monkeypatch.setattr(tools, "storage", test_storage)
    return test_storage


def test_log_activity_and_history(temp_store):
    tools.tool_log_activity("test_user", "transport", "car_petrol_medium", 10)
    tools.tool_log_activity("test_user", "food", "beef", 1)

    history = tools.tool_get_history("test_user", "week")
    assert history["activity_count"] == 2
    assert history["total_co2e_kg"] == pytest.approx(1.92 + 7.2)
    assert "transport" in history["by_category"]
    assert "food" in history["by_category"]


def test_log_activity_unknown_returns_error(temp_store):
    result = tools.tool_log_activity("test_user", "transport", "rocket", 1)
    assert "error" in result


def test_suggest_swaps_beef_to_chicken(temp_store):
    tools.tool_log_activity("test_user", "food", "beef", 4)

    result = tools.tool_suggest_swaps("test_user", top_n=3)
    assert result["suggestions"], "expected at least one swap suggestion"
    top = result["suggestions"][0]
    assert top["current_activity"] == "Beef"
    assert top["alternative_activity"] == "Chicken / poultry"
    # 4 meals: beef 7.2*4=28.8, chicken 1.1*4=4.4 -> savings 24.4
    assert top["monthly_savings_kg_co2e"] == pytest.approx(24.4)


def test_suggest_swaps_ac_reduction(temp_store):
    tools.tool_log_activity("test_user", "energy", "ac_hour", 10)

    result = tools.tool_suggest_swaps("test_user", top_n=3)
    assert result["suggestions"]
    top = result["suggestions"][0]
    # 10 hours * 0.6 factor = 6 kg, 30% savings = 1.8
    assert top["monthly_savings_kg_co2e"] == pytest.approx(1.8)


def test_compare_to_average(temp_store):
    tools.tool_log_activity("test_user", "transport", "car_petrol_medium", 100)
    result = tools.tool_compare_to_average("test_user", "global")
    assert result["annual_kg"] > 0
    assert "vs_paris_target_pct" in result
