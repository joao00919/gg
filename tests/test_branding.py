from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_key_panels_use_zynex_identity_without_dashboard_button():
    panel = (ROOT / "commands" / "admin" / "painel.py").read_text(encoding="utf-8")
    assert "ZYNEX Systems" in panel
    assert "Acesse a Dashboard" not in panel
    assert 'name="botconfig"' in panel


def test_required_renames_and_no_carteira_command():
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "commands").rglob("*.py"))
    assert 'name="gerarpix"' in text
    assert 'name="rank"' in text
    assert 'name="sync_clients"' in text
    assert 'name="carteira"' not in text


def test_ticket_review_placeholder_was_removed():
    text = (ROOT / "modules" / "tickets" / "functions" / "setup_functions" / "review.py").read_text(encoding="utf-8")
    assert "Lógica para avaliar aqui" not in text
    assert "save_ticket_review" in text
