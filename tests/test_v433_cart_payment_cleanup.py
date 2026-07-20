from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cart_uses_organized_product_blocks_and_no_cash_label():
    checkout = (ROOT / "modules/loja/cart/checkout.py").read_text(encoding="utf-8")
    assert "def _format_cart_products" in checkout
    assert "Produtos no carrinho • {len(items)} item(ns) • {total_units} unidade(s)" in checkout
    assert "Resumo do pedido" in checkout
    assert "Valor à vista" not in checkout


def test_payment_removes_duplicated_provider_and_safety_copy():
    payment = (ROOT / "modules/loja/cart/cart_handlers.py").read_text(encoding="utf-8")
    assert "Pagamento PIX gerado" in payment
    assert "Produtos no carrinho • {payment_total_units} unidade(s)" in payment
    assert "Não envie comprovantes ou dados pessoais" not in payment
    assert "Processado por:" not in payment
    assert "Valor à vista" not in payment


def test_payment_removes_manual_status_button_and_uses_custom_terms_emoji():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    handlers = (root / "modules/loja/cart/cart_handlers.py").read_text(encoding="utf-8")
    checkout = (root / "modules/loja/cart/checkout.py").read_text(encoding="utf-8")
    runtime = (root / "functions/interaction_runtime.py").read_text(encoding="utf-8")
    cancel = (root / "modules/loja/cart/cancel.py").read_text(encoding="utf-8")

    assert 'label="Atualizar status"' not in handlers
    assert 'getattr(emoji, "termos"' in checkout
    assert '"textc": "📋"' in runtime
    assert 'Pagamento aprovado com sucesso! Processando entrega' not in cancel
    assert 'await inter.delete_original_response()' in cancel
