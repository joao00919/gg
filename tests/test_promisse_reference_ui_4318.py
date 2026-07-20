from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_criar_uses_reference_name_option_and_direct_panel():
    source = _text("commands/zynex_commands.py")
    assert 'description="Coloque o NOME do produto!"' in source
    assert 'description="💰 | Vendas Moderação | Cadastra um novo produto no bot"' in source
    assert 'ConfigurarCampo.panel(inter, product_id, field_id)' in source
    assert 'O produto **{product_name}** foi criado com sucesso!' in source


def test_reference_product_panel_has_same_actions_and_text():
    source = _text("modules/loja/products/product/campos/fields/configurar.py")
    for text in (
        "Informações do Produto",
        "Estilo da Entrega",
        "Condições atuais",
        "Cargos autorizados a comprar",
        'label="Editar"',
        'label="Estoque"',
        'label="Estilo de Entrega"',
        'label="Config.Extra"',
        'label="Configurações"',
        'label="Sincronizar"',
        'label="Deletar"',
    ):
        assert text in source


def test_reference_extra_and_advanced_panels_are_complete():
    source = _text("modules/loja/products/product/campos/fields/configurar.py")
    for text in (
        "Gerencie as condições extras deste produto.",
        "Editar Valores",
        "Resetar Cargos",
        "Selecione os cargos autorizados a comprar",
        "Gerencie as configurações avançadas deste produto.",
        "Configurações Avançadas",
        'label="Banner"',
        'label="Miniatura"',
        'label="Cargo"',
        'label="Cor Embed"',
        'label="Categoria"',
        "Desativar Cupons",
    ):
        assert text in source


def test_reference_stock_and_cart_buttons_are_restored():
    stock = _text("modules/loja/products/product/campos/fields/estoque/visualizar.py")
    checkout = _text("modules/loja/cart/checkout.py")
    payment = _text("modules/loja/cart/cart_handlers.py")
    for text in (
        "Gerencie os itens de estoque entregues após a compra deste campo.",
        "Estilo de Estoque",
        'label="Adicionar"',
        'label="Fantasma"',
        'label="Upload .txt"',
        'label="Ver estoque"',
        'label="Infinito"',
        'label="Limpar"',
    ):
        assert text in stock
    assert 'placeholder="Gerenciar produtos no carrinho"' in checkout
    assert 'label="Adicionar produtos"' not in checkout
    assert 'label="Atualizar carrinho"' not in checkout
    assert 'label="Cancelar compra"' not in checkout
    assert 'label="Código copia e cola"' in payment
    assert 'label="Atualizar status"' not in payment
    assert 'label="Cancelar pagamento"' in payment
    assert 'label="Aprovar Pagamento"' in payment


def test_zenyx2_is_global_interface_logo():
    source = _text("functions/emoji.py")
    for alias in ('"z0": "zenyx2"', '"logo": "zenyx2"', '"sales_logo": "zenyx2"'):
        assert alias in source
    assert (ROOT / "database/emojis/assets/zenyx2.png").is_file()
