import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_exact_brand_and_user_emoji_catalog():
    data = json.loads((ROOT / "database/emojis/emojis.json").read_text(encoding="utf-8"))
    assert data["zenyx2"] == "<:zenyx2:1527921690292785272>"
    assert data["online"] == "<:online:1525692156742864977>"
    assert data["ticket"] == "<:ticket:1525692241530847284>"
    assert data["pix"] == "<:pix:1525692180029509742>"
    assert data["loading"] == "<a:1389945080172904539:1527386782776164392>"
    assert not any("148431" in str(value) for value in data.values())


def test_promisse_cart_flow_and_buttons():
    checkout = text("modules/loja/cart/checkout.py")
    handlers = text("modules/loja/cart/cart_handlers.py")
    for label in (
        "Ir para pagamento", "Editar quantidade", "Usar cupom de desconto",
        "Ler Termos e Condições",
    ):
        assert f'label="{label}"' in checkout
    assert 'placeholder="Gerenciar produtos no carrinho"' in checkout
    for removed in ("Adicionar produtos", "Atualizar carrinho", "Cancelar compra"):
        assert f'label="{removed}"' not in checkout
    assert "Escolha a forma de pagamento" in handlers
    assert 'label="Pagar com PIX"' in handlers
    assert 'label="Pagar com Cartão de Crédito"' in handlers
    assert 'custom_id=f"cart_back_summary:' in handlers
    assert 'title="Alterar Quantidade"' in handlers
    assert 'label="NOVA QUANTIDADE"' in handlers


def test_promisse_product_panel_and_main_interface():
    product = text("modules/loja/products/product/campos/fields/configurar.py")
    main = text("commands/admin/painel.py")
    for label in (
        "Editar", "Estoque", "Estilo de Entrega", "Config.Extra",
        "Configurações", "Sincronizar", "Deletar", "Voltar",
    ):
        assert f'label="{label}"' in product
    assert "emoji.zenyx2" in product
    assert "emoji.zenyx2" in main
    assert "ZENYX Bot" in main
    assert "ZenyxClous" in main
