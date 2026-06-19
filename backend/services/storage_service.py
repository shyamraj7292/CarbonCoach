"""
Storage layer for users and logged activities.

Uses Firestore if GOOGLE_CLOUD_PROJECT / credentials are configured,
otherwise falls back to a local JSON file (backend/data/store.json) so the
app runs standalone without any GCP setup. Either way, data is only ever
written by real user activity — there is no seeded or simulated data.
"""

import json
import os
import uuid
from datetime import datetime, timezone

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "store.json")

DEFAULT_USER_ID = "default_user"

_DEFAULT_USER = {
    "user_id": DEFAULT_USER_ID,
    "name": "User",
    "country": "global",
    "goal_annual_kg": 2500,
    "created_at": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalJsonStorage:
    """Simple JSON-file backed storage for a single-user deployment."""

    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            self._write({"users": {}, "activities": []})

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # --- users ---

    def get_user(self, user_id: str) -> dict:
        data = self._read()
        user = data["users"].get(user_id)
        if user is None:
            user = {**_DEFAULT_USER, "user_id": user_id, "created_at": _now_iso()}
            data["users"][user_id] = user
            self._write(data)
        return user

    def update_user(self, user_id: str, fields: dict) -> dict:
        data = self._read()
        user = data["users"].get(user_id, {**_DEFAULT_USER, "user_id": user_id, "created_at": _now_iso()})
        user.update(fields)
        data["users"][user_id] = user
        self._write(data)
        return user

    # --- activities ---

    def add_activity(self, user_id: str, activity: dict) -> dict:
        data = self._read()
        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "timestamp": activity.get("timestamp") or _now_iso(),
            **activity,
        }
        data["activities"].append(record)
        self._write(data)
        return record

    def get_activities(self, user_id: str, since: str | None = None) -> list[dict]:
        data = self._read()
        items = [a for a in data["activities"] if a["user_id"] == user_id]
        if since:
            items = [a for a in items if a["timestamp"] >= since]
        return sorted(items, key=lambda a: a["timestamp"])


storage = LocalJsonStorage(_STORE_PATH)
