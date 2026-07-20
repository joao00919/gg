from __future__ import annotations

import os
import unittest
from copy import deepcopy
from unittest.mock import patch

os.environ.setdefault("MAIN_GUILD_ID", "123456789012345678")

from modules.loja.products.product.create import CreateProductModal, build_product_payload


class ProductCreationTests(unittest.TestCase):
    def test_complete_product_schema(self):
        payload = build_product_payload(
            product_id="PROD_123",
            name="  Netflix 30 dias  ",
            description="Acesso privado",
            banner="https://example.com/banner.png",
            hex_color="#5865F2",
            delivery_type="automatic",
        )
        self.assertEqual(payload["id"], "PROD_123")
        self.assertEqual(payload["name"], "Netflix 30 dias")
        self.assertEqual(payload["info"]["delivery_type"], "automatic")
        self.assertEqual(payload["info"]["purchasesIds"], [])
        self.assertEqual(payload["campos"], {})
        self.assertEqual(payload["related_products"], [])
        self.assertEqual(payload["automation"]["low_stock_threshold"], 5)

    def test_invalid_delivery_falls_back_to_automatic(self):
        payload = build_product_payload(
            product_id="P1",
            name="Produto",
            description=None,
            banner=None,
            hex_color=None,
            delivery_type="qualquer",
        )
        self.assertEqual(payload["info"]["delivery_type"], "automatic")


class _FakeResponse:
    def __init__(self):
        self.defer_kwargs = None

    async def defer(self, **kwargs):
        self.defer_kwargs = kwargs


class _FakeModalInteraction:
    def __init__(self):
        self.message = None
        self.response = _FakeResponse()
        self.text_values = {
            "product_name": "Produto criado pelo comando",
            "product_description": "Descrição de teste",
            "product_banner": "https://example.com/banner.png",
            "product_hex_color": "#5865F2",
        }
        self.resolved_values = {"product_delivery_type": ["manual"]}
        self.edits = []

    async def edit_original_message(self, **kwargs):
        self.edits.append(kwargs)


class ProductModalCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_slash_modal_creates_ephemeral_response_and_persists_product(self):
        store = {"custom_mode": {"mode": "components"}, "loja_products": {}}

        def get_document(name):
            return deepcopy(store.get(name, {}))

        def save_document(name, data):
            store[name] = deepcopy(data)

        inter = _FakeModalInteraction()
        with (
            patch("modules.loja.products.product.create.has_capability", return_value=True),
            patch("modules.loja.products.product.create.db.get_document", side_effect=get_document),
            patch("modules.loja.products.product.create.db.save_document", side_effect=save_document),
            patch("modules.loja.products.product.create.utils.gerar_id", return_value="PROD_TEST"),
            patch("modules.loja.products.product.create.ConfigurarProduto.panel", return_value={"components": []}),
        ):
            await CreateProductModal().callback(inter)

        self.assertEqual(inter.response.defer_kwargs, {"with_message": True, "ephemeral": True})
        self.assertIn("PROD_TEST", store["loja_products"])
        product = store["loja_products"]["PROD_TEST"]
        self.assertEqual(product["name"], "Produto criado pelo comando")
        self.assertEqual(product["info"]["delivery_type"], "automatic")
        self.assertTrue(inter.edits)


if __name__ == "__main__":
    unittest.main()
