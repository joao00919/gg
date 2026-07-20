from __future__ import annotations

import base64
from pathlib import Path

from core.create_bot import resolve_discord_client_id

ROOT = Path(__file__).resolve().parents[1]


def _fake_token(application_id: str) -> str:
    encoded = base64.urlsafe_b64encode(application_id.encode()).decode().rstrip("=")
    return f"{encoded}.fake.fake"


def test_token_application_id_overrides_stale_explicit_id(monkeypatch):
    real_id = "1525657633044955227"
    monkeypatch.setenv("DISCORD_CLIENT_ID", "111111111111111111")
    assert resolve_discord_client_id(_fake_token(real_id)) == real_id


def test_ws_manager_does_not_replace_global_event_loop_policy_on_import():
    source = (ROOT / "connections" / "ws_manager.py").read_text(encoding="utf-8")
    assert "asyncio.set_event_loop_policy" not in source


def test_critical_commands_use_robust_panel_response():
    panel = (ROOT / "commands" / "admin" / "painel.py").read_text(encoding="utf-8")
    commands = (ROOT / "commands" / "zynex_commands.py").read_text(encoding="utf-8")
    runtime = (ROOT / "functions" / "interaction_runtime.py").read_text(encoding="utf-8")
    assert "await respond_panel(inter, panel, ephemeral=True)" in panel
    assert "name=\"qrcode_personalizar\"" in commands
    assert "return await respond_panel" in commands
    assert "repetindo com emojis seguros" in runtime
