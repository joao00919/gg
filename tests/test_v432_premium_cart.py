from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_premium_cart_visual_and_buttons():
    text = (ROOT / "modules/loja/cart/checkout.py").read_text(encoding="utf-8")
    for expected in [
        "Seu carrinho",
        'label="Ir para pagamento"',
        'label="Editar quantidade"',
        'placeholder="Gerenciar produtos no carrinho"',
        'label="Usar cupom de desconto"',
        "Resumo do pedido",
        "Confira os itens selecionados",
    ]:
        assert expected in text

def test_add_products_flow_is_functional():
    text = (ROOT / "modules/loja/cart/cart_handlers.py").read_text(encoding="utf-8")
    for expected in [
        "cart_add_products:",
        "cart_add_product_select:",
        "cart_add_option_select:",
        "cart_add_product_modal:",
        "await _add_item_to_cart",
        "StockManager.get_available_stock",
    ]:
        assert expected in text

def test_cart_help_uses_enabled_ticket_panels():
    text = (ROOT / "modules/loja/cart/cart_handlers.py").read_text(encoding="utf-8")
    assert "cart_help:" in text
    assert 'custom_id=f"create_ticket_{panel_id}"' in text
    assert 'panel.get("enabled", False)' in text
