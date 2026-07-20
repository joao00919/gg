from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_delivery_is_sent_only_by_dm():
    source = (ROOT / "modules/loja/cart/delivery.py").read_text(encoding="utf-8")
    block = source[source.index("async def deliver_product_to_user"):source.index("async def _send_feedback_incentive")]
    assert "Entrega o produto exclusivamente na DM" in block
    assert "user.dm_channel or await user.create_dm()" in block
    assert "is_cart_thread=False" in block
    assert "await _send_delivery_payload(\n                thread" not in block


def test_cart_notice_redirects_to_dm_and_announces_close():
    source = (ROOT / "modules/loja/purchase_experience.py").read_text(encoding="utf-8")
    block = source[source.index("async def send_thread_delivery_notice"):source.index("def setup", source.index("async def send_thread_delivery_notice"))]
    assert "seu produto foi entregue na DM" in block
    assert 'label="Ir para DM"' in block
    assert "discord.com/channels/@me/" in block
    assert "fechado em <t:" in block


def test_approved_cart_closes_after_three_minutes():
    source = (ROOT / "modules/loja/cart/checkout.py").read_text(encoding="utf-8")
    assert "_close_approved_cart_later(thread, cart_id, close_delay)" in source
    assert "await thread.edit(locked=True, archived=True)" in source
    assert 'cart["auto_close_at"] = cart["approved_at"] + 180' in source


def test_auto_close_is_recovered_after_bot_restart():
    source = (ROOT / "events/on_ready.py").read_text(encoding="utf-8")
    assert 'status == "approved"' in source
    assert 'cart.get("auto_close_at")' in source
    assert "_close_approved_cart_later(thread, cart_id, remaining)" in source
