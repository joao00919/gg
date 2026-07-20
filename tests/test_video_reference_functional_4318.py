from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import disnake

from modules.loja.cart.checkout import build_promisse_cart_action_rows
from modules.loja.product_panels import build_admin_payload, build_products_payload
from modules.loja.products.product.campos.fields.configurar import ConfigurarCampo

ROOT = Path(__file__).resolve().parents[1]


def _load_painel_command():
    spec = importlib.util.spec_from_file_location("video_reference_painel", ROOT / "commands/admin/painel.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.PainelCommand


def _component_dicts(rows_or_components):
    return [component.to_component_dict() for component in rows_or_components]


def _walk(component):
    yield component
    for child in component.get("components", []) or []:
        yield from _walk(child)


def _labels(payload):
    labels = []
    for root in _component_dicts(payload["components"]):
        labels.extend(node.get("label") for node in _walk(root) if node.get("label"))
    return labels


def _custom_ids(payload):
    ids = []
    for root in _component_dicts(payload["components"]):
        ids.extend(node.get("custom_id") for node in _walk(root) if node.get("custom_id"))
    return ids


def _placeholders(payload):
    values = []
    for root in _component_dicts(payload["components"]):
        values.extend(node.get("placeholder") for node in _walk(root) if node.get("placeholder"))
    return values


def test_main_panel_matches_reference_button_grid_and_brand():
    fake_inter = SimpleNamespace(user=SimpleNamespace(name="Cliente"))
    states = {
        "loja": True,
        "ticket": True,
        "cloud": True,
        "rendimentos": True,
        "personalizacao": True,
        "automacoes": True,
        "protection": True,
        "sorteios": True,
        "configuracoes": True,
    }
    PainelCommand = _load_painel_command()
    components = PainelCommand(None).PainelComponents(fake_inter, button_states=states)
    payload = {"components": components}
    assert _labels(payload) == [
        "Configurar Loja",
        "Gerenciar Ticket",
        "ZenyxClous",
        "Proteção do Servidor",
        "Automações",
        "Configurações",
        "Sorteios",
    ]
    rendered = components[0].to_component_dict()
    rendered_text = json.dumps(rendered, ensure_ascii=False)
    assert "<:zenyx2:1527921690292785272>" in rendered_text
    assert "ZENYX Bot" in rendered_text


def test_product_create_panel_has_exact_reference_actions():
    product = {
        "name": "Produto Teste",
        "active": True,
        "info": {"delivery_type": "automatic", "hex_color": "#ADD8E6"},
        "campos": {
            "FIELD": {
                "id": "FIELD",
                "name": "Produto Teste",
                "price": 0.0,
                "description": None,
                "stock": [],
                "condicoes": {},
                "cargos": {"authorized": []},
            }
        },
    }
    store = {
        "loja_products": {"PRODUCT": product},
        "custom_mode": {"mode": "components"},
        "custom_colors": {"primary": "#ADD8E6"},
    }
    inter = SimpleNamespace(guild=None, bot=None)
    with (
        patch(
            "modules.loja.products.product.campos.fields.configurar.db.get_document",
            side_effect=lambda name: store.get(name, {}),
        ),
        patch(
            "modules.loja.products.product.campos.fields.configurar.StockManager.get_available_stock",
            return_value=0,
        ),
    ):
        payload = ConfigurarCampo.panel(inter, "PRODUCT", "FIELD")

    assert _labels(payload) == [
        "Editar",
        "Estoque",
        "Estilo de Entrega",
        "Config.Extra",
        "Configurações",
        "Sincronizar",
        "Deletar",
        "Voltar",
    ]
    content = json.dumps(_component_dicts(payload["components"]), ensure_ascii=False)
    for expected in (
        "Informações do Produto",
        "Preço: `R$ 0,00`",
        "Estoque: `0 Unidades`",
        "Estilo da Entrega: `Automático`",
        "Não configurado ainda...",
        "Condições atuais",
        "Todos Cargos",
    ):
        assert expected in content


def test_product_select_panel_matches_reference_and_is_functional():
    store = {
        "loja_product_panels": {
            "PANEL": {
                "id": "PANEL",
                "name": "Vitrine Principal",
                "description": "Escolha seu produto.",
                "product_ids": ["P1", "P2"],
                "product_emojis": {"P2": "<:gift:1525692079722860665>"},
                "active": True,
                "messages": [],
            }
        },
        "loja_products": {
            "P1": {"name": "Produto Um", "active": True, "campos": {"F1": {}}},
            "P2": {"name": "Produto Dois", "active": True, "campos": {"F2": {}}},
        },
        "custom_colors": {},
    }
    with patch("modules.loja.product_panels.db.get_document", side_effect=lambda name: store.get(name, {})):
        admin = build_admin_payload("PANEL")
        products = build_products_payload("PANEL")

    assert _labels(admin) == [
        "Configurar Embed",
        "Configurar Produtos",
        "Atualizar Painel",
        "Deletar",
        "Voltar",
    ]
    assert _labels(products) == [
        "Adicionar Produto",
        "Remover Produto",
        "Sequência",
        "Sincronizar",
        "Voltar",
    ]
    assert _placeholders(products) == ["Alterar Emoji do Produto"]
    assert "ZynexProductPanel_Products:PANEL" in _custom_ids(admin)
    assert "ZynexProductPanel_EmojiSelect:PANEL" in _custom_ids(products)
    rendered = json.dumps(_component_dicts(products["components"]), ensure_ascii=False)
    assert "Produtos cadastrados no Painel" in rendered
    assert "Produto Um" in rendered and "Produto Dois" in rendered
    assert "<:gift:1525692079722860665>" in rendered


def test_single_item_cart_has_only_reference_buttons():
    option = disnake.SelectOption(label="Produto", value="0")
    rows = build_promisse_cart_action_rows(
        thread_id=123,
        item_options=[option],
        available_payment_keys=["pix"],
        final_price=2.5,
    )
    data = _component_dicts(rows)
    labels = [node.get("label") for row in data for node in _walk(row) if node.get("label")]
    assert labels == [
        "Ir para pagamento",
        "Editar quantidade",
        "Usar cupom de desconto",
        "Ler Termos e Condições",
    ]
    assert "Atualizar carrinho" not in labels
    assert "Cancelar compra" not in labels
    assert "Adicionar produtos" not in labels


def test_multiple_item_cart_replaces_edit_button_with_manager_select():
    rows = build_promisse_cart_action_rows(
        thread_id=456,
        item_options=[
            disnake.SelectOption(label="Produto Um", value="0"),
            disnake.SelectOption(label="Produto Dois", value="1"),
        ],
        available_payment_keys=["pix"],
        final_price=10.0,
    )
    data = _component_dicts(rows)
    labels = [node.get("label") for row in data for node in _walk(row) if node.get("label")]
    placeholders = [node.get("placeholder") for row in data for node in _walk(row) if node.get("placeholder")]
    ids = [node.get("custom_id") for row in data for node in _walk(row) if node.get("custom_id")]
    assert labels == ["Ir para pagamento", "Usar cupom de desconto", "Ler Termos e Condições"]
    assert placeholders == ["Gerenciar produtos no carrinho"]
    assert "cart_manage_item:456" in ids


def test_every_reference_emoji_has_id_and_local_asset():
    emoji_db = json.loads((ROOT / "database/emojis/emojis.json").read_text(encoding="utf-8"))
    names = {
        "zenyx2", "swords", "time", "ticket", "textc", "termos", "voice_lock", "wallet",
        "unlock", "voice", "settings", "search", "truck", "trophy", "save", "wand",
        "warn", "route", "role", "web", "website", "rocket", "whatsapp", "wrong",
        "shield", "slash", "sound", "sparkles", "speech", "star", "online", "on",
        "thunder", "telegram", "off", "pagbank", "pause", "picpay", "pix", "play",
        "plus", "power", "pushin_pay", "red", "reload", "robot", "like", "loading",
        "lock", "mail2", "giveaway", "folder", "member", "nubank", "gift",
        "mercado_pago", "delete", "deslike", "dir", "dnd", "dollar", "fire", "back",
        "ban", "bank", "boost", "calendar", "card", "bulb", "chart", "cardbox", "cart",
        "chevron", "clock", "coin", "colors", "commands", "cloud", "config", "correct",
        "coupon", "announcement",
    }
    assert not (names - emoji_db.keys())
    for name in names:
        assert str(emoji_db[name]).startswith(("<:", "<a:")), name
        assert any((ROOT / "database/emojis/assets").glob(f"{name}.*")), name


def test_visible_component_custom_ids_have_listeners():
    product_actions = (ROOT / "modules/loja/products/product/promisse_actions.py").read_text(encoding="utf-8")
    panel_actions = (ROOT / "modules/loja/product_panels.py").read_text(encoding="utf-8")
    cart_actions = (ROOT / "modules/loja/cart/cart_handlers.py").read_text(encoding="utf-8")
    cancel_actions = (ROOT / "modules/loja/cart/cancel.py").read_text(encoding="utf-8")
    for prefix in (
        "Promisse_EditarProduto:", "Promisse_ToggleEntrega:", "Promisse_ConfigExtra:",
        "Promisse_Configuracoes:", "Promisse_Sincronizar:", "Promisse_Deletar:",
    ):
        assert prefix in product_actions
    for prefix in (
        "ZynexProductPanel_Edit:", "ZynexProductPanel_Products:",
        "ZynexProductPanel_AddOpen:", "ZynexProductPanel_RemoveOpen:",
        "ZynexProductPanel_EmojiSelect:", "ZynexProductPanel_Sequence:",
        "ZynexProductPanel_Sync:", "ZynexProductPanel_Delete:",
    ):
        assert prefix in panel_actions
    for prefix in (
        "cart_continue:", "cart_edit_items:", "cart_manage_item:",
        "cart_apply_coupon:", "cart_view_terms:", "check_payment:",
    ):
        assert prefix in cart_actions
    assert "cancel_checkout:" in cart_actions and "cancel_checkout:" in cancel_actions
    assert "approve_manual_pix:" in cart_actions and "approve_manual_pix:" in cancel_actions


def test_ticket_edit_panel_matches_reference_and_delete_flow_exists():
    from modules.tickets.config.edit_panel import SpecificPanelView_components

    store = {
        "tickets_config": {
            "panels": {
                "PANEL": {
                    "name": "Suporte",
                    "enabled": True,
                    "mode": "channel",
                    "office_hours": {"start_time": "08:00", "end_time": "18:00"},
                    "ai_enabled": False,
                    "message_id": 123,
                    "channel_id": 456,
                    "category_id": 789,
                    "has_pending_changes": True,
                }
            }
        },
        "custom_colors": {"primary": "#6D28D9"},
    }
    fake_bot = SimpleNamespace(get_channel=lambda _channel_id: SimpleNamespace(id=_channel_id))
    fake_inter = SimpleNamespace(bot=fake_bot)
    with patch("modules.tickets.config.edit_panel.db.get_document", side_effect=lambda name: store.get(name, {})):
        components = SpecificPanelView_components(fake_inter, "PANEL")

    payload = {"components": components}
    assert _labels(payload) == [
        "Editar Opções",
        "Editar Mensagens",
        "Modo: Canal",
        "Horário de Atendimento",
        "PromisseAI",
        "Preferências",
        "Definir Categoria",
        "Editar Canais",
        "Editar Cargos",
        "Atualizar Painel",
        "Deletar Painel",
        "Deletar Tickets",
        "Voltar",
    ]
    rendered = json.dumps(_component_dicts(components), ensure_ascii=False)
    for expected in (
        "Painel > Gerenciar Tickets > Editar Painel",
        "Modo de Atendimento",
        "Horário:",
        "PromisseAI:",
        "<:zenyx2:1527921690292785272>",
    ):
        assert expected in rendered

    ids = _custom_ids(payload)
    assert "TicketEdit_DeleteTickets_PANEL" in ids
    ticket_cog = (ROOT / "modules/tickets/config/cog.py").read_text(encoding="utf-8")
    assert 'action == "DeleteTickets"' in ticket_cog
    assert 'action == "ConfirmDeleteTickets"' in ticket_cog
    assert 'action == "CancelDeleteTickets"' in ticket_cog
