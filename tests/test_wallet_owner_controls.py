from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_store_fee_control_is_not_exposed_in_wallet_panel():
    source = (ROOT / "modules/settings/payments/wallet_panel.py").read_text(encoding="utf-8")
    assert 'label="Definir Taxa da Loja"' not in source
    assert 'custom_id="GlobalWallet_StoreFee"' not in source
    assert "class StoreFeeModal" not in source
    assert "Apenas o dono do bot pode definir a Taxa da Loja" not in source


def test_wallet_uses_requested_state_and_config_emojis():
    source = (ROOT / "modules/settings/payments/wallet_panel.py").read_text(encoding="utf-8")
    assert "status_emoji = emoji.on if active else emoji.off" in source
    assert "emoji=emoji.off if enabled else emoji.on" in source
    assert "• Responsabilidade Taxa:" in source
    assert 'label="Responsabilidade Taxa"' in source
    assert 'label="Exibir Extrato"' in source
    assert "emoji=emoji.config" in source


def test_requested_emojis_are_resolved_per_application():
    source = (ROOT / "functions/emoji.py").read_text(encoding="utf-8")
    assert '"online": "🟢"' in source
    assert '"z0": "zenyx2"' in source
    assert '"sales_logo": "zenyx2"' in source
    assert "_apply_aliases(emoji)" in source
    assert "IDs de outro bot" in source
