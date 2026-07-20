from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from functions.database import database as db
from modules.loja.cart.purchase_manager import PurchaseManager
from modules.loja.purchase_experience import get_purchase_review, save_purchase_review
from modules.tickets.purchase_link import selector_payload
from tests.helpers import isolated_database


def _seed_product():
    db.save_document(
        "loja_products",
        {
            "prod1": {
                "name": "Produto Teste",
                "info": {"delivery_type": "automatic"},
                "campos": {"opt1": {"name": "Plano Premium"}},
            }
        },
    )


def test_ticket_recovers_approved_cart_missing_from_purchase_history():
    with tempfile.TemporaryDirectory() as temp:
        with isolated_database(Path(temp) / "db.json"):
            db.save_document("loja_buys", {"purchases": {}})
            db.save_document("loja_loyalty_users", {})
            db.save_document("loja_loyalty_events", {"items": []})
            db.save_document("loja_loyalty_config", {"enabled": False})
            _seed_product()
            db.save_document(
                "loja_data",
                {
                    "carts": {
                        "cart-1": {
                            "status": "approved",
                            "approved_at": 1700000000,
                            "user_id": 123,
                            "guild_id": 999,
                            "payment_method": "pix",
                            "total_price": 25.0,
                            "discount_amount": 0,
                            "items": [
                                {
                                    "product_id": "prod1",
                                    "campo_id": "opt1",
                                    "quantity": 1,
                                    "price_per_unit": 25.0,
                                    "item_total": 25.0,
                                }
                            ],
                        }
                    }
                },
            )

            payload = selector_payload(
                123,
                "panel",
                {"ticket_mode": "purchase", "purchase_settings": {}},
            )
            select = payload["components"][0].children[0]
            assert len(select.options) == 1
            assert "Produto Teste" in select.options[0].description
            purchases = PurchaseManager.get_user_purchases(123)
            assert len(purchases) == 1
            assert purchases[0]["metadata"]["recovered_from_cart"] is True


def test_purchase_review_validates_owner_and_duplicate():
    with tempfile.TemporaryDirectory() as temp:
        with isolated_database(Path(temp) / "db.json"):
            db.save_document("loja_buys", {"purchases": {}})
            db.save_document("loja_data", {"carts": {}})
            db.save_document("loja_reviews", {"version": 1, "items": []})
            db.save_document("loja_loyalty_users", {})
            db.save_document("loja_loyalty_events", {"items": []})
            db.save_document("loja_loyalty_config", {"enabled": False})
            purchase_id = PurchaseManager.register_purchase(
                user_id=123,
                product_id="prod1",
                product_name="Produto Teste",
                field_id="opt1",
                field_name="Plano Premium",
                quantity=1,
                unit_price=25,
                total_price=25,
                discount_amount=0,
                final_price=25,
                payment_method="pix",
                metadata={"cart_id": "cart-2", "review_enabled": True},
            )

            with pytest.raises(PermissionError):
                save_purchase_review(
                    purchase_id=purchase_id,
                    user_id=999,
                    rating=5,
                    comment="Tentativa inválida",
                )

            review = save_purchase_review(
                purchase_id=purchase_id,
                user_id=123,
                rating=5,
                comment="Tudo certo",
            )
            assert review["rating"] == 5
            assert get_purchase_review(purchase_id)["comment"] == "Tudo certo"
            assert PurchaseManager.get_purchase_by_id(purchase_id)["review"]["submitted"] is True

            with pytest.raises(ValueError):
                save_purchase_review(
                    purchase_id=purchase_id,
                    user_id=123,
                    rating=4,
                    comment="Duplicada",
                )
