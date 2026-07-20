from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def test_standard_emojis_are_restored():
    data = json.loads((ROOT / "database/emojis/emojis.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/config_emoji.json").read_text(encoding="utf-8"))
    assert data["cart"] == "<:cart:1525692023540154520>"
    assert data["cardbox"] == "<:cardbox:1525692014870663330>"
    assert data["coin"] == "<:coin:1525692031836360796>"
    assert data["wallet"] == "<:wallet:1525692260879175791>"
    assert data["on"] == "<:on:1525692156176760975>"
    assert data["off"] == "<:off:1525692155736363189>"
    assert data["config"] == "<:config:1525692035103850597>"
    assert data["online"] == "<:online:1525692156742864977>"
    assert data["zenyx2"] == "<:zenyx2:1527921690292785272>"
    assert config["isConfigured"] is True

def test_payment_menu_is_back_in_settings_only():
    settings = (ROOT / "modules/settings/cog.py").read_text(encoding="utf-8")
    loja = (ROOT / "modules/loja/cog.py").read_text(encoding="utf-8")
    payments = (ROOT / "modules/settings/payments/cog.py").read_text(encoding="utf-8")
    assert settings.count('label="Formas de Pagamento"') == 2
    assert 'custom_id="Configuracoes_Pagamentos"' in settings
    assert 'placeholder="Selecione uma opção para configurar"' in settings
    assert 'label="Formas de Pagamento"' not in loja
    assert 'Painel > Configurações > **Formas de Pagamento**' in payments
    assert 'custom_id="Painel_Configuracoes"' in payments

def test_public_brand_is_zynex():
    panel = (ROOT / "commands/admin/painel.py").read_text(encoding="utf-8")
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "ZYNEX Systems" in panel
    assert 'BRAND = "ZYNEX Systems"' in bot
    assert ("Ap" + "ex Applications") not in panel
