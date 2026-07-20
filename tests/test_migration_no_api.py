from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from functions.database import database as db
from migrations.zynex_no_api import run_migrations
from tests.helpers import isolated_database


def test_migration_is_additive_and_does_not_touch_payment_documents():
    with tempfile.TemporaryDirectory() as temp:
        with isolated_database(Path(temp) / "db.json"):
            payment_configs = {"sync_wallet": {"enabled": True, "api_key": "secret", "cover_fee": False}}
            payment_tracking = {"abc": {"status": "pending", "provider": "sync_wallet"}}
            db.save_document("payment_configs", copy.deepcopy(payment_configs))
            db.save_document("payment_tracking", copy.deepcopy(payment_tracking))
            db.save_document("loja_products", {"p1": {"id": "p1", "name": "Produto", "info": {}, "campos": {}, "cupons": {}}})
            result = run_migrations(create_backup=False)
            assert result["applied"] is True
            assert db.get_document("payment_configs") == payment_configs
            assert db.get_document("payment_tracking") == payment_tracking
            product = db.get_document("loja_products")["p1"]
            assert product["active"] is True
            assert product["product_type"] == "digital"
            assert result["payment_api_changed"] is False
