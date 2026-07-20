from types import SimpleNamespace
import asyncio
from unittest.mock import patch


def _roots(payload):
    return [item.to_component_dict() for item in payload.get("components", [])]


def _walk(node):
    yield node
    for child in node.get("components", []) or []:
        yield from _walk(child)


def _nodes(payload):
    for root in _roots(payload):
        yield from _walk(root)


def _labels(payload):
    return [node.get("label") for node in _nodes(payload) if node.get("label")]


def _ids(payload):
    return [node.get("custom_id") for node in _nodes(payload) if node.get("custom_id")]


def _texts(payload):
    return "\n".join(str(node.get("content")) for node in _nodes(payload) if node.get("content"))


def _modal_labels(modal):
    labels = []
    for component in modal.components:
        node = component.to_component_dict()
        if node.get("label"):
            labels.append(node["label"])
        for child in node.get("components", []) or []:
            if child.get("label"):
                labels.append(child["label"])
    return labels


def _db(name):
    if name == "custom_mode":
        return {"mode": "components"}
    if name == "custom_colors":
        return {}
    if name == "loja_products":
        return {
            "P1": {
                "name": "Produto Exemplo",
                "info": {"description": "", "delivery_type": "automatic"},
                "campos": {"C1": {"price": 10.0, "stock": []}},
            }
        }
    return {}


def test_create_product_flow_matches_video_reference():
    from modules.loja.products.product.create import CreateProductAIModal, CreateProductModal, create_method_panel

    with patch("modules.loja.products.product.create.db.get_document", side_effect=_db):
        panel = create_method_panel(SimpleNamespace())
    assert _labels(panel) == ["Criar Manualmente", "Criar com IA", "Voltar"]
    assert set(_ids(panel)) >= {"Loja_CriarProduto_Manual", "Loja_CriarProduto_IA", "Loja_Produtos"}
    assert "Como você quer criar o produto?" in _texts(panel)
    assert _modal_labels(CreateProductModal()) == ["Nome do Produto", "Descrição do Produto", "Valor do Produto (R$)", "Banner do Produto (opcional)"]
    assert _modal_labels(CreateProductAIModal()) == ["O que você quer vender?", "Valor desejado (opcional)"]


def test_product_overview_has_video_buttons_and_sections():
    from modules.loja.products.product.configurar import ConfigurarProduto

    with patch("modules.loja.products.product.configurar.db.get_document", side_effect=_db):
        panel = ConfigurarProduto.panel(SimpleNamespace(), "P1")
    assert _labels(panel) == [
        "Editar", "Estoque", "Estilo de Entrega", "Config.Extra",
        "Configurações", "Sincronizar", "Deletar", "Voltar",
    ]
    text = _texts(panel)
    assert "Informações do Produto" in text
    assert "Condições atuais" in text
    assert "disponível para compra" in text


def test_personalization_purchase_subpanel_and_modals_match_video():
    from modules.loja.personalization.cog import (
        AfterPurchaseModal,
        FirstPurchaseModal,
        PersonalizarLoja,
        PurchaseMessageModal,
    )

    with patch("modules.loja.personalization.cog.db.get_document", side_effect=_db):
        panel = PersonalizarLoja.panel(SimpleNamespace())
        purchase = PersonalizarLoja.purchase_panel(SimpleNamespace())
        first = FirstPurchaseModal()
        after = AfterPurchaseModal()
        purchase_modal = PurchaseMessageModal()

    assert _labels(panel) == [
        "Mensagem de Compra", "Mensagem de Compra Aprovada",
        "Mensagem de Primeira Compra", "Mensagem Após Compra", "Voltar",
    ]
    assert _labels(purchase) == [
        "Configurar Mensagem de Compra", "Resetar Mensagem de Compra",
        "Atualizar Todas Mensagens de Compra", "Voltar",
    ]
    assert _modal_labels(purchase_modal) == ["Título da mensagem", "Mensagem da compra"]
    assert _modal_labels(first) == [
        "Mensagem (escreva 'não' pra desativar)",
        "Onde enviar: 'dm' ou ID do canal",
        "Texto do botão (opcional)",
        "Link do botão (opcional)",
    ]
    assert _modal_labels(after) == [
        "Mensagem (escreva 'não' pra desativar)",
        "Enviar após quantos segundos?",
        "Texto do botão (opcional)",
        "Link do botão (opcional)",
    ]


def test_approved_message_panel_has_style_json_and_button_controls():
    from modules.loja.personalization.cog import PersonalizarLoja

    with patch("modules.loja.personalization.cog.db.get_document", side_effect=_db):
        panel = PersonalizarLoja.approved_panel(SimpleNamespace())
    labels = _labels(panel)
    for expected in [
        "Importar JSON", "Visualizar", "Variáveis", "Desativar Comprar",
        "Desativar Feedbacks", "Emoji", "Label", "Voltar",
    ]:
        assert expected in labels
    assert "Loja_Approved_Style" in _ids(panel)
    text = _texts(panel)
    assert "Modo Atual" in text
    assert "Botões da Mensagem" in text


def test_preferences_and_terms_use_video_names():
    from modules.loja.preferences.cog import PreferenciasLoja
    from modules.loja.preferences.terms import TermsEditModal

    with (
        patch("modules.loja.preferences.cog.db.get_document", side_effect=_db),
        patch("modules.loja.preferences.cog._reviews_enabled", return_value=True),
    ):
        panel = PreferenciasLoja.panel(SimpleNamespace())
    assert "Gerencie as preferências globais da sua loja." in _texts(panel)
    assert _modal_labels(TermsEditModal()) == ["TERMOS DE COMPRA:"]
    assert TermsEditModal().title == "Alterar Termos De Compra"

class _Response:
    def __init__(self):
        self.sent = None
        self.edited = None
        self.modal = None
        self.deferred = None

    def is_done(self):
        return False

    async def send_message(self, *args, **kwargs):
        self.sent = (args, kwargs)

    async def edit_message(self, **kwargs):
        self.edited = kwargs

    async def send_modal(self, modal):
        self.modal = modal

    async def defer(self, **kwargs):
        self.deferred = kwargs


class _ModalInter:
    def __init__(self, values):
        self.text_values = values
        self.response = _Response()
        self.followup = SimpleNamespace(send=None)

    async def edit_original_message(self, **kwargs):
        self.response.edited = kwargs


class _Component:
    def __init__(self, custom_id):
        self.custom_id = custom_id


class _ClickInter:
    def __init__(self, custom_id, values=None):
        self.component = _Component(custom_id)
        self.values = values or []
        self.response = _Response()
        self.followup = SimpleNamespace(send=None)
        self.guild = None

    async def edit_original_message(self, **kwargs):
        self.response.edited = kwargs


def test_first_and_after_purchase_callbacks_persist_video_fields():
    from modules.loja.personalization.cog import AfterPurchaseModal, FirstPurchaseModal

    store = {"loja_personalization": {}, "custom_mode": {"mode": "components"}, "custom_colors": {}}

    def get_document(name):
        return store.get(name, {})

    def save_document(name, value):
        store[name] = value

    with (
        patch("modules.loja.personalization.cog.db.get_document", side_effect=get_document),
        patch("modules.loja.personalization.cog.db.save_document", side_effect=save_document),
        patch("modules.loja.personalization.cog.respond_panel") as respond,
    ):
        respond.return_value = None
        asyncio.run(FirstPurchaseModal().callback(_ModalInter({
            "message": "Bem-vindo!", "destination": "dm",
            "button_text": "Abrir", "button_url": "https://example.com",
        })))
        asyncio.run(AfterPurchaseModal().callback(_ModalInter({
            "message": "Avalie", "delay_seconds": "15",
            "button_text": "Avaliar", "button_url": "https://example.com/review",
        })))

    first = store["loja_personalization"]["first_purchase_message"]
    after = store["loja_personalization"]["after_purchase_message"]
    assert first == {
        "enabled": True, "message": "Bem-vindo!", "destination": "dm",
        "button_text": "Abrir", "button_url": "https://example.com",
    }
    assert after["enabled"] is True
    assert after["delay_seconds"] == 15
    assert store["loja_personalization"]["feedback_incentive"]["message"] == "Avalie"


def test_approved_style_callback_saves_selection_and_refreshes_panel():
    from modules.loja.personalization.cog import PersonalizarLoja

    store = {"loja_personalization": {}, "custom_mode": {"mode": "components"}, "custom_colors": {}}

    def get_document(name):
        return store.get(name, {})

    def save_document(name, value):
        store[name] = value

    inter = _ClickInter("Loja_Approved_Style", ["components"])
    cog = PersonalizarLoja(SimpleNamespace())
    with (
        patch("modules.loja.personalization.cog.db.get_document", side_effect=get_document),
        patch("modules.loja.personalization.cog.db.save_document", side_effect=save_document),
        patch("modules.loja.personalization.cog.respond_panel") as respond,
    ):
        respond.return_value = None
        asyncio.run(cog.on_dropdown(inter))
    assert store["loja_personalization"]["delivery_message"]["style"] == "components"
    respond.assert_awaited_once()

def test_stock_request_editor_matches_video_reference():
    from modules.loja.preferences.solicitar_estoque import StockRequestPreferences

    store = {
        "custom_mode": {"mode": "components"},
        "custom_colors": {},
        "loja_preferences": {"stock_requests": {"panel_message": {}}},
    }
    with patch(
        "modules.loja.preferences.solicitar_estoque.db.get_document",
        side_effect=lambda name: store.get(name, {}),
    ):
        panel = StockRequestPreferences.panel(SimpleNamespace())
    assert _labels(panel) == [
        "Definir mensagem", "Limpar", "Definir corpo do Embed", "Limpar",
        "Definir imagem", "Limpar", "Visualizar mensagem", "Postar mensagem", "Voltar",
    ]
    assert "Configuração atual" in _texts(panel)
    assert set(_ids(panel)) >= {
        "Loja_Stock_DefineMessage", "Loja_Stock_ClearMessage",
        "Loja_Stock_DefineEmbed", "Loja_Stock_ClearEmbed",
        "Loja_Stock_DefineImage", "Loja_Stock_ClearImage",
        "Loja_Stock_Preview", "Loja_Stock_Post", "Loja_Preferencias",
    }


def test_approved_delivery_payload_uses_saved_style_and_buttons():
    from modules.loja.purchase_experience import _build_delivery_payload

    config = {
        "delivery_message": {
            "style": "embed",
            "title": "Pedido {purchase_id} aprovado",
            "message": "Produto {product_name} — {delivery_status}",
            "buttons": {
                "buy": {"enabled": True, "label": "Comprar novamente", "emoji": "🛒"},
                "feedback": {"enabled": True, "label": "Avaliar", "emoji": "⭐"},
            },
        }
    }
    purchase = {"product": {"id": "P1"}}
    with (
        patch("modules.loja.purchase_experience.db.get_document", side_effect=lambda name: config if name == "loja_personalization" else {"enabled": True}),
        patch("modules.loja.purchase_experience.PurchaseManager.get_purchase_by_id", return_value=purchase),
    ):
        payload = _build_delivery_payload(
            purchase_id="ABC", product_name="Produto", field_name="Padrão",
            quantity=1, paid_value=10, delivered=True,
        )
    assert payload["embed"].title == "Pedido ABC aprovado"
    assert "Produto Produto — Entregue" in payload["embed"].description
    labels = [button.label for row in payload["components"] for button in row.children]
    assert labels == ["Comprar novamente", "Avaliar"]
