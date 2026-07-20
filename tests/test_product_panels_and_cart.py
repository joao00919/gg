from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from modules.loja.product_panels import create_panel, get_panels, panel_autocomplete_values

ROOT = Path(__file__).resolve().parents[1]


def test_create_panel_creates_empty_select_panel_not_product():
    store = {"loja_product_panels": {}, "loja_products": {"OLD": {"name": "Produto antigo"}}}

    def get_document(name):
        return deepcopy(store.get(name, {}))

    def save_document(name, data):
        store[name] = deepcopy(data)

    with (
        patch("modules.loja.product_panels.db.get_document", side_effect=get_document),
        patch("modules.loja.product_panels.db.save_document", side_effect=save_document),
        patch("modules.loja.product_panels.utils.gerar_id", return_value="PANEL_TEST"),
    ):
        panel_id, panel = create_panel("Vitrine Principal", 123)
        panels = get_panels()
        values = panel_autocomplete_values("vitrine")

    assert panel_id == "PANEL_TEST"
    assert panel["product_ids"] == []
    assert panels[panel_id]["name"] == "Vitrine Principal"
    assert values == ["Vitrine Principal — PANEL_TEST"]
    assert store["loja_products"] == {"OLD": {"name": "Produto antigo"}}


def test_criar_painel_command_uses_product_panel_manager():
    text = (ROOT / "commands" / "zynex_commands.py").read_text(encoding="utf-8")
    section = text[text.index('name="criar_painel"'):text.index('name="set_painel"')]
    assert "create_product_panel" in section
    assert "build_admin_payload" in section
    assert "ConfigurarProduto" not in section


def test_cart_has_direct_link_and_fee_preview():
    text = (ROOT / "modules" / "loja" / "cart" / "checkout.py").read_text(encoding="utf-8")
    assert 'label="Ir para o carrinho"' in text
    assert 'emoji=emoji.cart' in text
    assert "_integrated_wallet_preview" in text
    assert "Taxa da Loja" in text
    assert "Total no PIX" in text
    assert 'label="Ir para pagamento"' in text
