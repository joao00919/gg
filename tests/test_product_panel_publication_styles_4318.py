from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_product_publication_has_all_requested_styles():
    source = (ROOT / "modules/loja/products/product/send.py").read_text(encoding="utf-8")
    for label in (
        "Modo Texto Simples",
        "Modo Legacy",
        "Modo Legacy (Personalizado)",
        "Container (Imagem Fora)",
        "Container (Imagem Dentro)",
    ):
        assert label in source
    assert 'send_mode_text:' in source
    assert 'send_mode_legacy_basic:' in source


def test_product_description_is_normalized_from_old_records():
    source = (ROOT / "functions/loja_products.py").read_text(encoding="utf-8")
    assert "def get_product_description" in source
    assert 'field.get("description")' in source
    assert "def ensure_product_description" in source


def test_panel_has_description_banner_color_and_style_selector():
    source = (ROOT / "modules/loja/product_panels.py").read_text(encoding="utf-8")
    assert 'label="Descrição do Painel"' in source
    assert 'custom_id="panel_banner"' in source
    assert 'custom_id="panel_color"' in source
    assert "def build_publish_style_payload" in source
    assert "legacy_custom" in source
    assert "container_inside" in source
