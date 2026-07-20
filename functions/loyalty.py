from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

from functions.database import database as db

_LOCK = threading.RLock()
DEFAULT_CONFIG = {
    "enabled": True,
    "points_per_real": 1.0,
    "levels": [
        {"name": "Bronze", "min_points": 0},
        {"name": "Prata", "min_points": 500},
        {"name": "Ouro", "min_points": 1500},
        {"name": "Diamante", "min_points": 5000},
    ],
}


def _config() -> dict:
    config = db.get_document("loja_loyalty_config") or {}
    merged = dict(DEFAULT_CONFIG)
    merged.update(config)
    return merged


def _level(points: int, config: dict) -> str:
    selected = "Bronze"
    for level in sorted(config.get("levels", []), key=lambda item: int(item.get("min_points", 0))):
        if points >= int(level.get("min_points", 0)):
            selected = str(level.get("name") or selected)
    return selected


def get_profile(user_id: int | str) -> dict:
    users = db.get_document("loja_loyalty_users") or {}
    profile = dict(users.get(str(user_id)) or {})
    profile.setdefault("points", 0)
    profile.setdefault("level", _level(int(profile["points"]), _config()))
    return profile


def award_purchase_points(purchase_id: str, user_id: int | str, amount: float) -> dict:
    """Credita pontos uma vez por compra; não interfere no gateway de pagamento."""
    with _LOCK:
        raw_events = db.get_document("loja_loyalty_events")
        events = {"version": 1, "items": raw_events} if isinstance(raw_events, list) else (raw_events or {"version": 1, "items": []})
        items = events.setdefault("items", [])
        event_key = f"purchase:{purchase_id}"
        existing = next((item for item in items if item.get("key") == event_key), None)
        if existing:
            return {"created": False, "event": existing, "profile": get_profile(user_id)}
        config = _config()
        if not config.get("enabled", True):
            return {"created": False, "disabled": True, "profile": get_profile(user_id)}
        points = max(0, int(round(float(amount) * float(config.get("points_per_real", 1.0)))))
        users = db.get_document("loja_loyalty_users") or {}
        profile = dict(users.get(str(user_id)) or {"points": 0})
        profile["points"] = max(0, int(profile.get("points", 0)) + points)
        profile["level"] = _level(profile["points"], config)
        profile["updatedAt"] = datetime.now(timezone.utc).isoformat()
        users[str(user_id)] = profile
        event = {
            "key": event_key,
            "userId": str(user_id),
            "purchaseId": str(purchase_id),
            "type": "credit",
            "points": points,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        items.append(event)
        events["items"] = items[-10000:]
        db.save_document("loja_loyalty_users", users)
        db.save_document("loja_loyalty_events", events)
        return {"created": True, "event": event, "profile": profile}


def reverse_purchase_points(purchase_id: str, *, reason: str = "refund") -> dict:
    with _LOCK:
        raw_events = db.get_document("loja_loyalty_events")
        events = {"version": 1, "items": raw_events} if isinstance(raw_events, list) else (raw_events or {"version": 1, "items": []})
        items = events.setdefault("items", [])
        original = next((item for item in items if item.get("key") == f"purchase:{purchase_id}"), None)
        reversal_key = f"reversal:{purchase_id}"
        existing = next((item for item in items if item.get("key") == reversal_key), None)
        if existing or not original:
            return {"created": False, "event": existing}
        users = db.get_document("loja_loyalty_users") or {}
        user_id = str(original["userId"])
        profile = dict(users.get(user_id) or {"points": 0})
        profile["points"] = max(0, int(profile.get("points", 0)) - int(original.get("points", 0)))
        profile["level"] = _level(profile["points"], _config())
        profile["updatedAt"] = datetime.now(timezone.utc).isoformat()
        users[user_id] = profile
        event = {"key": reversal_key, "userId": user_id, "purchaseId": str(purchase_id), "type": "debit", "points": -int(original.get("points", 0)), "reason": reason, "createdAt": datetime.now(timezone.utc).isoformat()}
        items.append(event)
        db.save_document("loja_loyalty_users", users)
        db.save_document("loja_loyalty_events", events)
        return {"created": True, "event": event, "profile": profile}
