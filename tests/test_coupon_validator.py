from __future__ import annotations

import tempfile
from pathlib import Path

from functions.database import database as db
from modules.loja.cart.coupon_validator import CouponValidator
from tests.helpers import isolated_database


def test_fixed_discount_limit_and_per_user_limit():
    with tempfile.TemporaryDirectory() as temp:
        with isolated_database(Path(temp) / "db.json"):
            db.save_document("loja_products", {
                "p1": {"cupons": {"c1": {
                    "name": "ZYNEX10", "active": True, "discount_type": "fixed",
                    "discount_value": 10, "max_discount": 8, "max_uses_per_user": 1,
                    "used_by": [], "allowed_products": ["p1"],
                }}}
            })
            valid, _, discount, _ = CouponValidator.validate_product_coupon("zynex10", "p1", 5, 20.0)
            assert valid is True
            assert discount == 8.0
            CouponValidator.use_product_coupon("p1", "ZYNEX10", 5)
            valid, message, _, _ = CouponValidator.validate_product_coupon("ZYNEX10", "p1", 5, 20.0)
            assert valid is False
            assert "limite" in message.lower()
