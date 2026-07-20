from __future__ import annotations

from typing import Any

PRIORITIES = ("normal", "high", "urgent")

DEFAULT_AUTOMATION_RULES = {
    "enabled": True,
    "stock": {
        "enabled": True,
        "threshold": 5,
        "notify_admin": True,
        "mark_low_stock": True,
        "disable_promotion": True,
        "channel_id": None,
    },
    "payment": {
        "deliver_product": True,
        "add_points": True,
        "update_vip": True,
        "send_receipt": True,
        "enable_review": True,
        "points_per_real": 1,
    },
    "tickets": {
        "enabled": True,
        "stale_minutes": 30,
        "mention_support": True,
        "raise_priority": True,
    },
}


def merge_rules(stored: dict | None) -> dict:
    stored = stored or {}
    merged = {"enabled": stored.get("enabled", True)}
    for section, defaults in DEFAULT_AUTOMATION_RULES.items():
        if section == "enabled":
            continue
        merged[section] = {**defaults, **(stored.get(section) or {})}
    return merged


def escalate_priority(current: str | None) -> str:
    current = str(current or "normal").lower()
    if current not in PRIORITIES:
        current = "normal"
    index = PRIORITIES.index(current)
    return PRIORITIES[min(index + 1, len(PRIORITIES) - 1)]


def stock_is_low(quantity: Any, threshold: Any = 5) -> bool:
    try:
        return int(quantity) < max(0, int(threshold))
    except (TypeError, ValueError):
        return False


def is_ticket_stale(ticket: dict, now: int, stale_minutes: int = 30) -> bool:
    if ticket.get("status") != "open":
        return False
    base = ticket.get("last_staff_response_timestamp") or ticket.get("last_activity_timestamp") or ticket.get("created_at")
    try:
        return now - int(base) >= max(1, int(stale_minutes)) * 60
    except (TypeError, ValueError):
        return False
