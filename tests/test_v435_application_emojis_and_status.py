from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_brand_asset_and_application_sync_are_enabled():
    assert (ROOT / "database/emojis/assets/zenyx2.png").is_file()
    state = json.loads((ROOT / "database/emojis/emojis_data.json").read_text(encoding="utf-8"))
    assert state["configured"] == "True"
    source = (ROOT / "functions/emojis/__init__.py").read_text(encoding="utf-8")
    assert "applications/{self.app_id}/emojis" in source
    assert "BRAND_EMOJI_NAME = \"zenyx2\"" in source


def test_status_is_fixed_to_zenyx_system():
    source = (ROOT / "tasks/bot/status_rotator.py").read_text(encoding="utf-8")
    assert 'STATUS_TEXT = "💖 Zenyx System"' in source
    template = json.loads((ROOT / "database_template.json").read_text(encoding="utf-8"))
    assert template["custom_status"]["names"] == ["💖 Zenyx System"]


def test_no_foreign_loading_emoji_literals_in_runtime_code():
    forbidden = "<a:1389945080172904539:1527386782776164392>"
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        assert forbidden not in path.read_text(encoding="utf-8", errors="ignore"), path
