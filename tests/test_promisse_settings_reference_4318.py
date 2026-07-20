from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json

from modules.settings.cog import Settings
from modules.settings.payments.cog import ConfigurarPagamentos
from modules.settings.payments.wallet_panel import GlobalWalletPanel
from modules.loja.cart.checkout import build_promisse_cart_action_rows
import disnake

ROOT = Path(__file__).resolve().parents[1]

def _dicts(components):
    return [item.to_component_dict() for item in components]

def _walk(item):
    yield item
    for child in item.get("components", []) or []:
        yield from _walk(child)

def _labels(components):
    return [node["label"] for root in _dicts(components) for node in _walk(root) if node.get("label")]

def _options(components):
    result=[]
    for root in _dicts(components):
        for node in _walk(root):
            result.extend(option.get("label") for option in node.get("options", []) or [])
    return result

def test_settings_panel_matches_observed_reference():
    with patch("modules.settings.cog.db.get_document", side_effect=lambda name: {"primary": "#5c5ef0"} if name == "custom_colors" else {}):
        components = Settings(None).settings_components(SimpleNamespace())
    assert _labels(components) == ["Formas de Pagamento", "Voltar"]
    assert _options(components) == ["Moderação", "Notificações", "Configurar Bot", "Configurar Mensagens", "Configurar Canais", "Configurar Cargos"]
    text=json.dumps(_dicts(components), ensure_ascii=False)
    assert "Selecione uma opção para configurar" in text
    assert "Configure e personalize os canais, cargos e formas de pagamento." in text

def test_payment_provider_select_matches_reference_names():
    with patch("modules.settings.payments.cog.db.get_document", return_value={}):
        components = ConfigurarPagamentos.pagamentos_components(SimpleNamespace())
    assert _options(components)[:5] == ["Carteira Integrada", "Mistic Pay", "Semi-Automático", "Mercado Pago", "Efi Bank"]
    text=json.dumps(_dicts(components), ensure_ascii=False)
    assert "Selecione uma forma de pagamento" in text
    assert "Configure as formas de pagamento disponíveis para seus clientes." in text

def test_terms_button_uses_requested_custom_emoji():
    rows = build_promisse_cart_action_rows(thread_id=1, item_options=[disnake.SelectOption(label="P", value="0")], available_payment_keys=["pix"], final_price=1)
    data=json.dumps(_dicts(rows), ensure_ascii=False)
    assert "Ler Termos e Condições" in data
    assert "1528340290039976107" in data

def test_wallet_panel_has_reference_actions():
    async def fake_balance():
        return 0.07, None
    with patch.object(GlobalWalletPanel, "_balance", fake_balance), patch("modules.settings.payments.wallet_panel.global_wallet_is_configured", return_value=True), patch("modules.settings.payments.wallet_panel.db.get_document", side_effect=lambda name: {"sync_wallet": {"enabled": True, "fee_responsibility": "store"}} if name == "payment_configs" else ({"primary": "#5c5ef0"} if name == "custom_colors" else ({"mode": "components"} if name == "custom_mode" else {}))):
        import asyncio
        payload=asyncio.run(GlobalWalletPanel.payload(SimpleNamespace()))
    labels=_labels(payload["components"] if isinstance(payload, list) else payload["components"])
    assert labels == ["Desligar Carteira Integrada", "Saque", "Responsabilidade Taxa", "Exibir Extrato", "Voltar"]
