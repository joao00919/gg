from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_set_publishes_existing_product_and_opens_style_selector():
    source = (ROOT / "commands" / "zynex_commands.py").read_text(encoding="utf-8")
    start = source.index('name="set",')
    end = source.index('name="criar_painel"', start)
    section = source[start:end]
    assert 'description="💰 | Vendas Moderação | Publique um produto já criado"' in section
    assert 'autocomplete=product_autocomplete' in section
    assert '_build_mode_selector' in section
    assert 'CreateProductModal' not in section


def test_set_painel_opens_style_selector_for_existing_panel():
    source = (ROOT / "commands" / "zynex_commands.py").read_text(encoding="utf-8")
    start = source.index('name="set_painel"')
    end = source.index('name="criarcupom"', start)
    section = source[start:end]
    assert 'description="💰 | Vendas Moderação | Publique um painel já criado"' in section
    assert 'autocomplete=panel_autocomplete' in section
    assert 'build_publish_style_payload' in section


def test_loading_uses_requested_animated_emoji():
    source = (ROOT / "database" / "emojis" / "emojis.json").read_text(encoding="utf-8")
    assert '<a:1389945080172904539:1527386782776164392>' in source
