from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_wallet_withdraw_modal_and_note_removed():
    text = _text("modules/settings/payments/wallet_panel.py")
    assert 'title="Realizar Saque"' in text
    assert 'text="Chave Pix"' in text
    assert 'text="Valor do Saque"' in text
    assert 'text="Estilo de Saque"' in text
    assert 'Retirada Turbo (R$ 1,50) - Imediata' in text
    assert 'A Taxa da Loja é somada à cobrança' not in text


def test_cloud_local_verification_is_functional():
    cog = _text("modules/cloud/cog.py")
    local = _text("modules/cloud/local_verification.py")
    assert 'Cloud_SetVerifiedRole' in cog
    assert 'Cloud_GetAuthLink' in cog
    assert 'await verify_member(inter.user, self.bot)' in cog
    assert 'await member.add_roles(role' in local
    assert 'verification_mode' in local


def test_cart_checkout_has_loading_lock_and_video_reference_actions():
    handlers = _text("modules/loja/cart/cart_handlers.py")
    checkout = _text("modules/loja/cart/checkout.py")
    assert 'await inter.response.defer(ephemeral=True)' in handlers
    assert 'Quase lá! Preparando os detalhes do pagamento' in handlers
    assert 'checkout_processing' in handlers
    assert 'label="Ir para pagamento"' in checkout
    assert 'label="Editar quantidade"' in checkout
    assert 'placeholder="Gerenciar produtos no carrinho"' in checkout
    assert 'label="Atualizar carrinho"' not in checkout
    assert 'label="Cancelar compra"' not in checkout


def test_customer_term_uses_option_instead_of_field():
    handlers = _text("modules/loja/cart/cart_handlers.py")
    checkout = _text("modules/loja/cart/checkout.py")
    assert 'Campo: `{campo_name}`' not in handlers
    assert '**Opção selecionada:** `{option_name[:80]}`' in checkout
    assert 'Produto sem opções disponíveis' in checkout



def test_cloud_is_available_in_basic_plan_and_events_load():
    plan = _text("functions/plan.py")
    cloud_init = _text("modules/cloud/__init__.py")
    assert 'if module_name == "cloud"' in plan
    assert 'if button_name == "cloud"' in plan
    assert 'CloudEvents' in cloud_init


def test_cart_actions_are_split_like_reference_for_single_and_multiple_items():
    checkout = _text("modules/loja/cart/checkout.py")
    assert 'def build_promisse_cart_action_rows' in checkout
    assert 'ActionRow(continue_button, edit_button)' in checkout
    assert 'ActionRow(manager_select)' in checkout
    assert 'ActionRow(coupon_button, terms_button)' in checkout


def test_cart_continue_has_global_error_guard_and_stale_lock_recovery():
    handlers = _text("modules/loja/cart/cart_handlers.py")
    assert 'await self._process_cart_continue(inter)' in handlers
    assert 'await self._handle_cart_continue_error(inter, exc)' in handlers
    assert 'is_recent_lock' in handlers
    assert 'O carrinho foi liberado para uma nova tentativa' in handlers


def test_visible_product_field_term_is_clearer():
    buy_modal = _text("modules/loja/cart/buy_modal.py")
    panels = _text("modules/loja/products/product/campos/panels.py")
    assert 'Selecione o Campo' not in buy_modal
    assert 'Selecione a Opção do Produto' in buy_modal
    assert 'Selecione um campo para gerenciar' not in panels


def test_cart_continue_reads_custom_id_inside_handler():
    handlers = _text("modules/loja/cart/cart_handlers.py")
    marker = 'async def _process_cart_continue'
    block = handlers.split(marker, 1)[1].split('async def ', 1)[0]
    assert 'custom_id = str(getattr(getattr(inter, "component", None), "custom_id", "") or "")' in block
    assert 'thread_id = int(parts[1])' in block


def test_no_customer_facing_campo_word_remains():
    visible_files = [
        "modules/rendimentos/cog.py",
        "modules/settings/extensions/cog.py",
        "modules/loja/cart/buy_modal.py",
        "modules/loja/categories/configurar.py",
        "modules/loja/products/product/campos/panels.py",
        "modules/loja/products/product/campos/categories/configurar.py",
        "commands/vendas/entregar.py",
    ]
    forbidden = [
        "  Campo: ", " | Campos: ", "Selecione um campo", "Nenhum campo",
        "campos selecionáveis", "seletor de campos", "campo desejado",
    ]
    for rel in visible_files:
        content = _text(rel)
        for term in forbidden:
            assert term not in content, f"{term!r} ainda aparece em {rel}"
