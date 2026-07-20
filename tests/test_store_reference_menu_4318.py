from types import SimpleNamespace
from unittest.mock import patch


def _dicts(payload):
    return [item.to_component_dict() for item in payload.get("components", [])]


def _walk(node):
    yield node
    for child in node.get("components", []) or []:
        yield from _walk(child)


def _nodes(payload):
    for root in _dicts(payload):
        yield from _walk(root)


def _labels(payload):
    return [node["label"] for node in _nodes(payload) if node.get("label")]


def _ids(payload):
    return [node["custom_id"] for node in _nodes(payload) if node.get("custom_id")]


def _select_options(payload, custom_id):
    for node in _nodes(payload):
        if node.get("custom_id") == custom_id:
            return node.get("options") or []
    return []


def test_store_panel_matches_requested_sections_and_buttons():
    from modules.loja.cog import Loja

    with (
        patch("modules.loja.cog.db.get_document", side_effect=lambda name: {"mode": "components"} if name == "custom_mode" else {}),
        patch("modules.loja.cog.sales_enabled", return_value=True),
    ):
        payload = Loja(None).panel(SimpleNamespace())

    assert _labels(payload) == ["Desligar Vendas", "Templates", "Voltar"]
    assert _ids(payload) == ["Loja_Select", "Loja_ToggleSales", "Loja_Templates", "PainelInicial"]
    options = _select_options(payload, "Loja_Select")
    assert [item["label"] for item in options] == [
        "Gerenciar Produtos",
        "Personalizar Loja",
        "Preferências",
        "Extensões",
        "Sistema de Saldo",
        "Cashback",
        "Programa de Indicação",
    ]
    assert [item["value"] for item in options] == [
        "produtos", "personalizar", "preferencias", "extensoes", "saldo", "cashback", "afiliados"
    ]


def test_product_manager_contains_product_and_panel_sections():
    from modules.loja.products.cog import GerenciarProdutos

    store = {
        "custom_mode": {"mode": "components"},
        "custom_colors": {},
        "loja_products": {
            "P1": {"name": "Produto 1", "campos": {}, "active": True},
            "P2": {"name": "Produto 2", "campos": {}, "active": True},
        },
    }
    panels = {"A1": {"name": "Painel 1", "product_ids": ["P1"], "active": True}}
    with (
        patch("modules.loja.products.cog.db.get_document", side_effect=lambda name: store.get(name, {})),
        patch("modules.loja.products.cog.get_panels", return_value=panels),
        patch("modules.loja.products.cog.sales_enabled", return_value=True),
    ):
        payload = GerenciarProdutos(None).panel(SimpleNamespace())

    labels = _labels(payload)
    assert "Criar Produto" in labels
    assert "Criar Painel" in labels
    ids = _ids(payload)
    assert "Loja_CriarProduto" in ids
    assert "Loja_CriarPainel" in ids
    assert any(item.startswith("Loja_Produtos_Select:") for item in ids)
    assert any(item.startswith("Loja_Paineis_Select:") for item in ids)


def test_personalization_has_four_reference_message_buttons():
    from modules.loja.personalization.cog import PersonalizarLoja

    with patch(
        "modules.loja.personalization.cog.db.get_document",
        side_effect=lambda name: {"mode": "components"} if name == "custom_mode" else {},
    ):
        payload = PersonalizarLoja.panel(SimpleNamespace())

    assert _labels(payload) == [
        "Mensagem de Compra",
        "Mensagem de Compra Aprovada",
        "Mensagem de Primeira Compra",
        "Mensagem Após Compra",
        "Voltar",
    ]
    assert set(_ids(payload)) >= {
        "Loja_Message:purchase",
        "Loja_Message:approved",
        "Loja_Message:first_purchase",
        "Loja_Message:after_purchase",
        "Painel_Loja",
    }


def test_preferences_has_reference_options():
    from modules.loja.preferences.cog import PreferenciasLoja

    with (
        patch("modules.loja.preferences.cog.db.get_document", side_effect=lambda name: {"mode": "components"} if name == "custom_mode" else {}),
        patch("modules.loja.preferences.cog._reviews_enabled", return_value=True),
    ):
        payload = PreferenciasLoja.panel(SimpleNamespace())

    options = _select_options(payload, "Loja_Preferencias_Select")
    assert [item["label"] for item in options] == [
        "Alterar Estilo Carrinho",
        "Botão Dúvidas",
        "Termos de Compra",
        "Gerenciar BlackList",
        "Sistema solicitar estoque",
        "Sistema de Rank de Vendas",
        "Desligar Avaliação",
    ]
