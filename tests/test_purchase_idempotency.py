from __future__ import annotations

import tempfile
from pathlib import Path

from functions.database import database as db
from modules.loja.cart.purchase_manager import PurchaseManager
from tests.helpers import isolated_database


def _register():
    return PurchaseManager.register_purchase(
        user_id=10,
        product_id="p1",
        product_name="Produto",
        field_id="f1",
        field_name="Plano",
        quantity=1,
        unit_price=10.0,
        total_price=10.0,
        discount_amount=0.0,
        final_price=10.0,
        payment_method="pix",
        metadata={"cart_id": "cart-123"},
    )


def test_duplicate_confirmation_returns_same_purchase_and_points_once():
    with tempfile.TemporaryDirectory() as temp:
        with isolated_database(Path(temp) / "db.json"):
            db.save_document("loja_buys", {"purchases": {}})
            db.save_document("loja_loyalty_users", {})
            db.save_document("loja_loyalty_events", {"items": []})
            db.save_document("loja_loyalty_config", {"enabled": True, "points_per_real": 1.0})
            first = _register()
            second = _register()
            assert first == second
            assert len(PurchaseManager.get_all_purchases()) == 1
            assert db.get_document("loja_loyalty_users")["10"]["points"] == 10
            events = db.get_document("loja_loyalty_events")
            event_items = events if isinstance(events, list) else events["items"]
            assert len(event_items) == 1
