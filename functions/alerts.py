from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from functions.database import database as db

ALERT_TYPES = frozenset({
    "large_sale", "low_stock", "payment_failure", "payment_mismatch",
    "delivery_error", "ticket_unattended", "backup_failure", "internal_error",
})


def record_alert(alert_type: str, message: str, *, guild_id=None, details: dict[str, Any] | None = None) -> str:
    if alert_type not in ALERT_TYPES:
        raise ValueError(f"Tipo de alerta inválido: {alert_type}")
    raw = db.get_document("zynex_alerts")
    document = {"version": 1, "items": raw} if isinstance(raw, list) else (raw or {"version": 1, "items": []})
    items = document.setdefault("items", [])
    alert_id = f"{alert_type}:{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    items.append({
        "id": alert_id,
        "type": alert_type,
        "message": str(message)[:1000],
        "guildId": str(guild_id) if guild_id is not None else None,
        "details": details or {},
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "delivered": False,
    })
    document["items"] = items[-1000:]
    db.save_document("zynex_alerts", document)
    return alert_id
