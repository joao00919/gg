from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cart_has_complete_controls_and_item_manager():
    text = (ROOT / "modules/loja/cart/checkout.py").read_text(encoding="utf-8")
    assert "Seu carrinho" in text
    assert "cart_edit_items:" in text
    assert 'label="Ir para pagamento"' in text
    assert 'placeholder="Gerenciar produtos no carrinho"' in text
    assert 'label="Cancelar compra"' not in text
    assert "Ler Termos e Condições" in text


def test_pix_checkout_has_copy_and_cancel_buttons_without_manual_status():
    text = (ROOT / "modules/loja/cart/cart_handlers.py").read_text(encoding="utf-8")
    assert 'label="Código copia e cola"' in text
    assert 'label="Cancelar pagamento"' in text
    assert 'label="Atualizar status"' not in text
    assert 'custom_id.startswith("check_payment:")' in text
    assert "Pagamento PIX gerado" in text


def test_manual_status_check_calls_existing_payment_pipeline():
    text = (ROOT / "modules/loja/cart/cart_handlers.py").read_text(encoding="utf-8")
    assert "_check_single_payment_status" in text
    assert "_handle_payment_approved" in text
