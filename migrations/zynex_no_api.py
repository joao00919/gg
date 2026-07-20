from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from functions.database import database as db
from functions.database_backup import create_database_backup

MIGRATION_ID = "001_zynex_applications_no_api_v4"

DEFAULT_DOCUMENTS: dict[str, Any] = {
    "zynex_audit_log": {"events": []},
    "zynex_alerts": {"version": 1, "items": []},
    "zynex_alerts_config": {"enabled": True, "channel_id": None, "owner_dm": True},
    "zynex_monthly_reports": {"competencies": {}},
    "zynex_backup_metadata": {"last_backup": None},
    "loja_loyalty_users": {},
    "loja_loyalty_events": {"version": 1, "items": []},
    "loja_loyalty_config": {
        "enabled": True,
        "points_per_real": 1.0,
        "levels": [
            {"name": "Bronze", "min_points": 0},
            {"name": "Prata", "min_points": 500},
            {"name": "Ouro", "min_points": 1500},
            {"name": "Diamante", "min_points": 5000},
        ],
    },
    "loja_reviews": {"version": 1, "items": []},
    "ticket_reviews": {"version": 1, "items": []},
    "loja_promotions": {"version": 1, "items": []},
}


def _normalize_product(product_id: str, product: dict) -> bool:
    changed = False
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "internal_id": str(product.get("id") or product_id),
        "active": True,
        "product_type": "digital",
        "rating_average": 0.0,
        "rating_count": 0,
        "promotion": {"active": False, "price": None, "starts_at": None, "ends_at": None, "limit": None, "uses": 0},
        "audit": [],
        "created_at_iso": now,
        "updated_at_iso": now,
    }
    for key, value in defaults.items():
        if key not in product:
            product[key] = value
            changed = True
    info = product.setdefault("info", {})
    if "delivery_type" not in info:
        info["delivery_type"] = "manual"
        changed = True
    for coupon in (product.get("cupons") or {}).values():
        coupon_defaults = {
            "discount_type": "percentage",
            "discount_value": coupon.get("percent", 0),
            "max_discount": None,
            "starts_at": None,
            "max_uses_per_user": 1,
            "used_by": [],
            "allowed_products": [product_id],
            "allowed_categories": [],
        }
        for key, value in coupon_defaults.items():
            if key not in coupon:
                coupon[key] = value
                changed = True
    return changed


def run_migrations(*, create_backup: bool = True) -> dict:
    """Migração aditiva. Não lê nem grava documentos do gateway de pagamento."""
    state = db.get_document("zynex_migrations") or {"applied": {}}
    applied = state.setdefault("applied", {})
    if MIGRATION_ID in applied:
        return {"applied": False, "migration": MIGRATION_ID, "reason": "already_applied"}

    backup = None
    if create_backup:
        backup = create_database_backup(reason=f"pre_migration:{MIGRATION_ID}")

    created_documents = []
    for name, default in DEFAULT_DOCUMENTS.items():
        if not db.get_document(name):
            db.save_document(name, default)
            created_documents.append(name)

    products = db.get_document("loja_products") or {}
    products_changed = 0
    for product_id, product in products.items():
        if isinstance(product, dict) and _normalize_product(str(product_id), product):
            products_changed += 1
    if products_changed:
        db.save_document("loja_products", products)

    applied_at = datetime.now(timezone.utc).isoformat()
    applied[MIGRATION_ID] = {
        "appliedAt": applied_at,
        "backup": backup,
        "productsChanged": products_changed,
        "createdDocuments": created_documents,
        "paymentApiChanged": False,
    }
    state["applied"] = applied
    db.save_document("zynex_migrations", state)
    return {
        "applied": True,
        "migration": MIGRATION_ID,
        "backup": backup,
        "products_changed": products_changed,
        "created_documents": created_documents,
        "payment_api_changed": False,
    }
