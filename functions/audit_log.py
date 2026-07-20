from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid
from typing import Any

from functions.database import database as db

_SENSITIVE_KEY = re.compile(r"token|secret|password|api[_-]?key|authorization|pix|credential", re.I)


def _sanitize(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "***"
    if isinstance(value, dict):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value[:100]]
    text = str(value) if isinstance(value, Exception) else value
    if isinstance(text, str) and len(text) > 1000:
        return text[:997] + "..."
    return text


def write_audit_log(action: str, *, guild_id=None, user_id=None, admin_id=None, order_id=None, payment_id=None, result: str = "ok", error=None, details=None) -> str:
    correlation_id = uuid.uuid4().hex
    document = db.get_document("zynex_audit_log") or {"events": []}
    events = document.setdefault("events", [])
    events.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlationId": correlation_id,
        "action": str(action),
        "guildId": str(guild_id) if guild_id is not None else None,
        "userId": str(user_id) if user_id is not None else None,
        "adminId": str(admin_id) if admin_id is not None else None,
        "orderId": str(order_id) if order_id is not None else None,
        "paymentId": str(payment_id) if payment_id is not None else None,
        "result": result,
        "error": _sanitize(error, "error") if error else None,
        "details": _sanitize(details or {}, "details"),
    })
    document["events"] = events[-5000:]
    db.save_document("zynex_audit_log", document)
    return correlation_id
