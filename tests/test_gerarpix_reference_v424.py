from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_gerarpix_has_promisse_options_in_order():
    text = (ROOT / "commands" / "admin" / "function_payment.py").read_text(encoding="utf-8")
    assert 'description="🪙 | Vendas | Gere uma cobrança"' in text
    command = text.split('name="gerarpix"', 1)[1].split('async def _monitor_payment', 1)[0]
    positions = [command.index(token) for token in [
        "valor: Optional[float]",
        "produto: Optional[str]",
        "quantidade: Optional[int]",
        "usuario: Optional[disnake.Member]",
    ]]
    assert positions == sorted(positions)
    assert "Produto a vender; ao ser pago gera uma venda real (entrega + anúncio)" in command
    assert '"provider": "sync_wallet"' in command


def test_supplied_emojis_are_fixed_and_not_overwritten():
    data = json.loads((ROOT / "database" / "emojis" / "emojis.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs" / "config_emoji.json").read_text(encoding="utf-8"))
    assert data["pix"] == "<:pix:1525692180029509742>"
    assert data["wrong"] == "<:wrong:1525692278587527199>"
    assert data["settings2"] == "<:1389955124889124896:1527435783382761602>"
    assert data["coin"] == "<:coin:1525692031836360796>"
    assert data["zenyx2"] == "<:zenyx2:1527921690292785272>"
    assert "z0" not in data
    assert config["isConfigured"] is True


def test_product_payment_runs_real_sale_flow():
    text = (ROOT / "commands" / "admin" / "function_payment.py").read_text(encoding="utf-8")
    assert "_finish_product_sale" in text
    assert "deliver_product_to_user" in text
    assert "PurchaseManager.register_purchase" in text
    assert "send_purchase_event" in text
    assert "approved_pending_delivery" in text
