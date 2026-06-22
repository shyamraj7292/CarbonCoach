"""Integration tests for the FastAPI routes using TestClient."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from services import storage_service, tools


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    store_path = tmp_path / "store.json"
    store_path.write_text(json.dumps({"users": {}, "activities": []}))
    test_storage = storage_service.LocalJsonStorage(str(store_path))
    monkeypatch.setattr(storage_service, "storage", test_storage)
    monkeypatch.setattr(tools, "storage", test_storage)

    from routes import dashboard, insights, onboard
    from services import agent_service as agent_mod
    monkeypatch.setattr(dashboard, "storage", test_storage)
    monkeypatch.setattr(onboard, "storage", test_storage)
    monkeypatch.setattr(agent_mod.agent_service, "client", None)
    return test_storage


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_chat_fallback(client):
    res = client.post("/api/chat", json={"message": "drove 10km to work"})
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert isinstance(data["actions"], list)


def test_dashboard_summary_empty(client):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["today_kg"] == 0
    assert data["week_kg"] == 0


def test_dashboard_history(client):
    res = client.get("/api/dashboard/history?days=7")
    assert res.status_code == 200
    data = res.json()
    assert len(data["series"]) == 7


def test_insights_empty(client):
    res = client.get("/api/insights")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data


def test_onboard_get_and_post(client):
    res = client.get("/api/onboard")
    assert res.status_code == 200
    assert res.json()["country"] == "global"

    res = client.post("/api/onboard", json={"country": "india", "goal_annual_kg": 2000})
    assert res.status_code == 200
    assert res.json()["country"] == "india"
    assert res.json()["goal_annual_kg"] == 2000

    res = client.get("/api/onboard")
    assert res.json()["country"] == "india"


def test_chat_then_dashboard_updates(client):
    client.post("/api/chat", json={"message": "drove 20km"})
    res = client.get("/api/dashboard/summary")
    data = res.json()
    assert data["today_kg"] > 0
