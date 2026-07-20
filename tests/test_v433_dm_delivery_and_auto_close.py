from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_approved_message_has_direct_dm_button():
    text = (ROOT / "modules/loja/cart/checkout.py").read_text(encoding="utf-8")
    assert 'label="Ir para DM"' in text
    assert 'url=f"https://discord.com/channels/@me/{int(dm_channel_id)}"' in text
    assert "Produto entregue na sua DM" in text


def test_automatic_delivery_does_not_publish_stock_in_cart():
    text = (ROOT / "modules/loja/cart/delivery.py").read_text(encoding="utf-8")
    block = text[text.index("async def deliver_product_to_user"):text.index("async def _send_feedback_incentive")]
    assert "Dados sensíveis do produto nunca são publicados" in block
    assert "is_cart_thread=True" not in block
