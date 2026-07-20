"""
Handlers para botões do carrinho de compras
"""
import disnake
import asyncio
import io
from disnake.ext import commands
from datetime import datetime
from typing import Optional, Dict, Any
from functions.database import database as db
from functions.emoji import emoji
from .checkout import _build_cart_message, _add_item_to_cart, _create_payment, _extract_urls, _extract_qr_image, _extract_payment_ids, _http_get_bytes, _api_base_root, _money_br, _format_cart_products, _chunk_buttons
from .coupon_validator import CouponValidator
from .buy_modal import get_available_payment_methods, ensure_emoji
from .stock_manager import StockManager
from functions.promotions import get_effective_price


class CartPaymentMethodModal(disnake.ui.Modal):
    """Modal para seleção do método de pagamento do carrinho."""
    
    def __init__(self, cart_id: str):
        self.cart_id = str(cart_id)
        
        available_methods = get_available_payment_methods()
        components = []
        
        if available_methods:
            options = []
            for method_key, method_info in available_methods.items():
                payment_emoji = ensure_emoji(method_info["emoji"])
                options.append(
                    disnake.SelectOption(
                        label=method_info["label"],
                        value=method_key,
                        description=method_info["description"],
                        emoji=payment_emoji,
                    )
                )
            
            components.append(
                disnake.ui.Label(
                    text="Método de Pagamento",
                    component=disnake.ui.StringSelect(
                        placeholder="Selecione o método de pagamento",
                        custom_id="payment_method",
                        options=options,
                        required=True,
                    ),
                    description="Escolha como deseja pagar o carrinho",
                )
            )
        
        super().__init__(
            title="Escolher Forma de Pagamento",
            components=components,
            custom_id=f"cart_payment_modal:{self.cart_id}",
        )
    
    async def callback(self, inter: disnake.ModalInteraction):
        """Atualiza o método de pagamento do carrinho."""
        # Evitar timeout: defer logo no início
        if not inter.response.is_done():
            await inter.response.defer(ephemeral=True)

        custom_id = inter.custom_id or ""
        parts = custom_id.split(":")
        cart_id = parts[1] if len(parts) >= 2 else None
        if not cart_id:
            await inter.followup.send(
                f"{emoji.wrong} Carrinho não encontrado.",
                ephemeral=True,
            )
            return
        
        valores = inter.resolved_values
        payment_value = valores.get("payment_method")
        
        if isinstance(payment_value, (list, tuple)):
            payment_method = payment_value[0] if payment_value else None
        else:
            payment_method = payment_value or None
        
        if not payment_method:
            await inter.followup.send(
                f"{emoji.wrong} Selecione um método de pagamento válido.",
                ephemeral=True,
            )
            return
        
        # Carregar carrinho
        loja_data = db.get_document("loja_data")
        cart = loja_data.get("carts", {}).get(cart_id)
        
        if not cart:
            await inter.followup.send(
                f"{emoji.wrong} Carrinho não encontrado!",
                ephemeral=True,
            )
            return
        
        if int(cart.get("user_id", 0)) != int(inter.user.id):
            await inter.followup.send(
                f"{emoji.wrong} Este não é o seu carrinho!",
                ephemeral=True,
            )
            return
        
        # Atualizar método de pagamento
        cart["payment_method"] = payment_method
        cart["updated_at"] = int(datetime.utcnow().timestamp())
        
        loja_data["carts"][cart_id] = cart
        db.save_document("loja_data", loja_data)
        
        # Atualizar mensagem do carrinho
        thread_id = cart.get("thread_id")
        thread = inter.guild.get_thread(thread_id) if thread_id else None
        if thread:
            mode = db.get_document("custom_mode").get("mode", "embed")
            cart_msg_id = cart.get("cart_message_id")
            if cart_msg_id:
                try:
                    cart_msg = await thread.fetch_message(cart_msg_id)
                    new_cart_msg = await _build_cart_message(cart, thread, mode)
                    await cart_msg.delete()
                    cart["cart_message_id"] = new_cart_msg.id
                    loja_data["carts"][cart_id] = cart
                    db.save_document("loja_data", loja_data)
                except Exception:
                    pass
        
        method_names = {"pix": "PIX", "card": "Cartão de Crédito", "crypto": "Criptomoeda"}
        pretty_name = method_names.get(payment_method, payment_method.upper())
        
        await inter.followup.send(
            f"{emoji.correct} Método de pagamento atualizado para `{pretty_name}`!",
            ephemeral=True,
        )


class CartButtonHandlers(commands.Cog):
    """Handlers para botões do carrinho"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _quantity_modal(thread_id: str, item_idx: int, current_quantity: int) -> disnake.ui.Modal:
        """Modal de quantidade no mesmo padrão visual mostrado no vídeo."""
        return disnake.ui.Modal(
            title="Alterar Quantidade",
            custom_id=f"cart_edit_quantity_modal:{thread_id}:{item_idx}",
            components=[
                disnake.ui.TextInput(
                    label="NOVA QUANTIDADE",
                    placeholder="Coloque a nova quantidade do produto",
                    custom_id="new_quantity",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    min_length=1,
                    max_length=10,
                    value=str(max(1, int(current_quantity or 1))),
                )
            ],
        )

    @staticmethod
    def _cart_products_and_total(cart: Dict[str, Any]) -> tuple[str, int, float]:
        products = db.get_document("loja_products") or {}
        items = cart.get("items", []) or []
        product_text, total_units = _format_cart_products(items, products, limit=10)
        subtotal = sum(float(item.get("item_total", 0) or 0) for item in items)
        discount = float(cart.get("discount_amount", 0) or 0)
        balance = float(cart.get("balance_applied", 0) or 0)
        total = max(0.0, subtotal - discount - balance)
        return product_text, total_units, total

    async def _show_payment_choices(self, inter: disnake.MessageInteraction, thread_id: str) -> None:
        """Troca o resumo pela seleção PIX/Cartão usada na referência."""
        loja_data = db.get_document("loja_data") or {}
        cart = (loja_data.get("carts") or {}).get(str(thread_id))
        if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
            await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            return
        if str(cart.get("status") or "cart") != "cart":
            await inter.response.send_message(
                f"{emoji.wrong} Este carrinho já está em processo de pagamento!", ephemeral=True
            )
            return
        product_lines, total_units, total = self._cart_products_and_total(cart)
        available = get_available_payment_methods() or {}
        pix_available = "pix" in available or total <= 0
        card_available = "card" in available

        member = inter.guild.get_member(int(cart.get("user_id", 0))) if inter.guild else None
        author_name = getattr(member, "display_name", None) or getattr(inter.user, "display_name", "Cliente")
        author_icon = getattr(getattr(member or inter.user, "display_avatar", None), "url", None)
        colors = db.get_document("custom_colors") or {}
        try:
            embed_color = disnake.Colour(int(str(colors.get("primary") or "5865F2").replace("#", ""), 16))
        except Exception:
            embed_color = disnake.Color.blurple()

        embed = disnake.Embed(
            title=f"{getattr(emoji, 'wallet', '💳')} Escolha a forma de pagamento",
            description=(
                "Selecione uma das opções abaixo para gerar o pagamento do seu pedido."
            ),
            color=embed_color,
        )
        if author_icon:
            embed.set_author(name=author_name, icon_url=author_icon)
        else:
            embed.set_author(name=author_name)
        embed.add_field(
            name=f"Resumo do carrinho • {total_units} unidade(s)",
            value=product_lines[:1024],
            inline=False,
        )
        embed.add_field(
            name="Total do pedido",
            value=f"{emoji.coin} `{_money_br(total)}`",
            inline=False,
        )
        if inter.guild:
            icon_url = getattr(getattr(inter.guild, "icon", None), "url", None)
            if icon_url:
                embed.set_footer(text=inter.guild.name, icon_url=icon_url)
            else:
                embed.set_footer(text=inter.guild.name)
        embed.timestamp = datetime.utcnow()

        rows = [
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Pagar com PIX",
                    emoji=ensure_emoji(emoji.pix),
                    style=disnake.ButtonStyle.green,
                    custom_id=f"cart_pay_pix:{thread_id}",
                    disabled=not pix_available,
                ),
                disnake.ui.Button(
                    label="Pagar com Cartão de Crédito",
                    emoji=ensure_emoji(emoji.card),
                    style=disnake.ButtonStyle.primary,
                    custom_id=f"cart_pay_card:{thread_id}",
                    disabled=not card_available,
                ),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    emoji=ensure_emoji(emoji.back),
                    style=disnake.ButtonStyle.grey,
                    custom_id=f"cart_back_summary:{thread_id}",
                )
            ),
        ]
        await inter.response.edit_message(embed=embed, components=rows)

    async def _restore_cart_summary(self, inter: disnake.MessageInteraction, thread_id: str) -> None:
        loja_data = db.get_document("loja_data") or {}
        cart = (loja_data.get("carts") or {}).get(str(thread_id))
        if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
            await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            return
        await inter.response.defer()
        thread = inter.guild.get_thread(int(thread_id)) if inter.guild else None
        if thread is None and inter.guild:
            try:
                fetched = await inter.guild.fetch_channel(int(thread_id))
                thread = fetched if isinstance(fetched, disnake.Thread) else None
            except Exception:
                thread = None
        if thread is None:
            await inter.followup.send(f"{emoji.wrong} Canal do carrinho não encontrado.", ephemeral=True)
            return
        mode = (db.get_document("custom_mode") or {}).get("mode", "embed")
        new_message = await _build_cart_message(cart, thread, mode)
        try:
            await inter.message.delete()
        except Exception:
            pass
        cart["cart_message_id"] = new_message.id
        cart["updated_at"] = int(datetime.utcnow().timestamp())
        loja_data.setdefault("carts", {})[str(thread_id)] = cart
        db.save_document("loja_data", loja_data)

    @commands.Cog.listener("on_button_click")
    async def on_cart_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Handler para alterar método de pagamento do carrinho
        if custom_id.startswith("cart_change_payment:"):
            thread_id = int(custom_id.split(":")[1])
            cart_id = str(thread_id)
            
            # Verificar métodos disponíveis primeiro (operação rápida)
            available_methods = get_available_payment_methods()
            if not available_methods:
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            f"{emoji.wrong} Nenhum método de pagamento está disponível no momento. Entre em contato com um administrador.",
                            ephemeral=True
                        )
                    else:
                        await inter.followup.send(
                            f"{emoji.wrong} Nenhum método de pagamento está disponível no momento. Entre em contato com um administrador.",
                            ephemeral=True
                        )
                except:
                    pass
                return
            
            # Criar modal (operação rápida)
            modal = CartPaymentMethodModal(cart_id)
            
            # Tentar abrir modal imediatamente
            try:
                if not inter.response.is_done():
                    await inter.response.send_modal(modal)
                else:
                    # Se já foi respondida, não podemos enviar modal
                    await inter.followup.send(
                        f"{emoji.wrong} Não foi possível abrir o modal. Tente novamente.",
                        ephemeral=True
                    )
            except disnake.errors.NotFound:
                # Interação expirou - tentar enviar mensagem de erro
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                    else:
                        await inter.followup.send(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                except:
                    pass
            except Exception as e:
                # Outro erro - tentar enviar mensagem de erro
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            f"{emoji.wrong} Erro ao abrir modal: {str(e)}",
                            ephemeral=True
                        )
                    else:
                        await inter.followup.send(
                            f"{emoji.wrong} Erro ao abrir modal: {str(e)}",
                            ephemeral=True
                        )
                except:
                    pass
            return
        
        # Abre um menu privado para editar os produtos do carrinho.
        if custom_id.startswith("cart_edit_items:"):
            thread_id = custom_id.split(":", 1)[1]
            cart_id = str(thread_id)
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(cart_id)
            if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
                await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
                return
            if str(cart.get("status") or "cart") != "cart":
                await inter.response.send_message(
                    f"{emoji.interrogation} Este carrinho já avançou para o pagamento.", ephemeral=True
                )
                return
            items = cart.get("items") or []
            if not items:
                await inter.response.send_message(f"{emoji.wrong} O carrinho está vazio.", ephemeral=True)
                return
            # No carrinho com um produto, o vídeo abre o modal diretamente.
            if len(items) == 1:
                current_quantity = max(1, int(items[0].get("quantity", 1) or 1))
                await inter.response.send_modal(self._quantity_modal(thread_id, 0, current_quantity))
                return
            products = db.get_document("loja_products") or {}
            options = []
            for idx, item in enumerate((cart.get("items") or [])[:25]):
                product = products.get(item.get("product_id"), {}) or {}
                campo = (product.get("campos") or {}).get(item.get("campo_id"), {}) or {}
                name = str(product.get("name") or "Produto")
                option_name = str(campo.get("name") or "Opção")
                qty = max(1, int(item.get("quantity", 1) or 1))
                total = float(item.get("item_total", 0) or 0)
                options.append(
                    disnake.SelectOption(
                        label=name[:100],
                        value=str(idx),
                        description=f"{option_name} • {qty}x • {_money_br(total)}"[:100],
                        emoji=ensure_emoji(getattr(emoji, "cardbox", emoji.cart)),
                    )
                )
            if not options:
                await inter.response.send_message(f"{emoji.wrong} O carrinho está vazio.", ephemeral=True)
                return
            await inter.response.send_message(
                content=(
                    f"{getattr(emoji, 'edit', emoji.config)} **Editar itens do carrinho**\n"
                    "Selecione um produto para alterar a quantidade ou removê-lo."
                ),
                components=[
                    disnake.ui.ActionRow(
                        disnake.ui.StringSelect(
                            placeholder="Selecione o produto que deseja editar",
                            custom_id=f"cart_manage_item:{thread_id}",
                            options=options,
                            min_values=1,
                            max_values=1,
                        )
                    )
                ],
                ephemeral=True,
            )
            return

        # Permite continuar comprando sem criar outro carrinho.
        if custom_id.startswith("cart_add_products:"):
            thread_id = custom_id.split(":", 1)[1]
            cart_id = str(thread_id)
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(cart_id)
            if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
                await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
                return
            if str(cart.get("status") or "cart") != "cart":
                await inter.response.send_message(
                    f"{emoji.interrogation} Não é possível adicionar produtos após gerar o pagamento.", ephemeral=True
                )
                return
            products = db.get_document("loja_products") or {}
            product_options = []
            for product_id, product in products.items():
                if not isinstance(product, dict) or not product.get("active", True):
                    continue
                campos = product.get("campos") or {}
                valid_campos = [(cid, c) for cid, c in campos.items() if isinstance(c, dict)]
                if not valid_campos:
                    continue
                prices = []
                for _campo_id, campo in valid_campos:
                    try:
                        prices.append(float(get_effective_price(product, campo) or 0))
                    except Exception:
                        pass
                start_price = min(prices) if prices else 0.0
                description = f"{len(valid_campos)} opção(ões) • a partir de {_money_br(start_price)}"
                product_options.append(
                    disnake.SelectOption(
                        label=str(product.get("name") or "Produto")[:100],
                        value=str(product_id),
                        description=description[:100],
                        emoji=ensure_emoji(getattr(emoji, "cardbox", emoji.cart)),
                    )
                )
                if len(product_options) >= 25:
                    break
            if not product_options:
                await inter.response.send_message(
                    f"{emoji.wrong} Nenhum produto adicional está disponível no momento.", ephemeral=True
                )
                return
            await inter.response.send_message(
                content=(
                    f"{getattr(emoji, 'plus', emoji.cart)} **Adicionar produtos**\n"
                    "Escolha um produto. Ele será incluído neste mesmo carrinho."
                ),
                components=[
                    disnake.ui.ActionRow(
                        disnake.ui.StringSelect(
                            placeholder="Escolha um produto para adicionar",
                            custom_id=f"cart_add_product_select:{thread_id}",
                            options=product_options,
                            min_values=1,
                            max_values=1,
                        )
                    )
                ],
                ephemeral=True,
            )
            return

        # Central de ajuda contextual do carrinho.
        if custom_id.startswith("cart_help:"):
            thread_id = custom_id.split(":", 1)[1]
            cart_id = str(thread_id)
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(cart_id)
            if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
                await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
                return
            tickets_config = db.get_document("tickets_config") or {}
            panels = tickets_config.get("panels") or {}
            support_buttons = []
            try:
                from modules.tickets.purchase_link import mode_requires_purchase
            except Exception:
                mode_requires_purchase = lambda _panel: False
            for panel_id, panel in panels.items():
                if not isinstance(panel, dict) or not panel.get("enabled", False):
                    continue
                if mode_requires_purchase(panel):
                    continue
                button_data = panel.get("button") or {}
                support_buttons.append(
                    disnake.ui.Button(
                        label=str(button_data.get("label") or panel.get("name") or "Abrir atendimento")[:80],
                        emoji=ensure_emoji(button_data.get("emoji") or getattr(emoji, "ticket", None)),
                        style=disnake.ButtonStyle.green,
                        custom_id=f"create_ticket_{panel_id}",
                    )
                )
                if len(support_buttons) >= 5:
                    break
            content = (
                f"{getattr(emoji, 'ticket', emoji.interrogation)} **Ajuda com o carrinho**\n\n"
                f"• Use **Editar Itens** para alterar quantidade ou remover produtos.\n"
                f"• Use **Adicionar Produtos** para continuar comprando no mesmo carrinho.\n"
                f"• Use **Atualizar** se algum valor não aparecer corretamente.\n"
                f"• O pagamento e a entrega acontecerão neste mesmo canal privado."
            )
            if support_buttons:
                await inter.response.send_message(
                    content=content + "\n\n**Precisa falar com a equipe?**",
                    components=[disnake.ui.ActionRow(*support_buttons)],
                    ephemeral=True,
                )
            else:
                await inter.response.send_message(
                    content=content + "\n\nNão há painel de atendimento comum ativo no momento.",
                    ephemeral=True,
                )
            return

        # Atualiza o resumo sem criar outra thread ou cobrança.
        if custom_id.startswith("cart_refresh:"):
            thread_id = int(custom_id.split(":", 1)[1])
            cart_id = str(thread_id)
            await inter.response.defer(ephemeral=True)
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(cart_id)
            if not cart:
                return await inter.followup.send(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            if int(cart.get("user_id", 0)) != int(inter.user.id):
                return await inter.followup.send(f"{emoji.wrong} Este não é o seu carrinho.", ephemeral=True)
            if cart.get("status") != "cart":
                return await inter.followup.send(
                    f"{emoji.interrogation} Este carrinho já avançou para o pagamento.", ephemeral=True
                )
            thread = inter.guild.get_thread(thread_id) if inter.guild else None
            if thread is None and inter.guild:
                try:
                    fetched = await inter.guild.fetch_channel(thread_id)
                    thread = fetched if isinstance(fetched, disnake.Thread) else None
                except Exception:
                    thread = None
            if thread is None:
                return await inter.followup.send(f"{emoji.wrong} O canal do carrinho não foi encontrado.", ephemeral=True)
            mode = (db.get_document("custom_mode") or {}).get("mode", "embed")
            old_id = cart.get("cart_message_id")
            new_msg = await _build_cart_message(cart, thread, mode)
            cart["cart_message_id"] = new_msg.id
            cart["updated_at"] = int(datetime.utcnow().timestamp())
            loja_data.setdefault("carts", {})[cart_id] = cart
            db.save_document("loja_data", loja_data)
            if old_id:
                try:
                    old_msg = await thread.fetch_message(int(old_id))
                    await old_msg.delete()
                except Exception:
                    pass
            await inter.followup.send(f"{emoji.correct} Carrinho atualizado.", ephemeral=True)
            return

        # Primeiro passo do checkout: exibe a seleção igual ao vídeo.
        if custom_id.startswith("cart_continue:"):
            await self._show_payment_choices(inter, custom_id.split(":", 1)[1])
            return

        # Pagamento escolhido na tela intermediária.
        if custom_id.startswith(("cart_pay_pix:", "cart_pay_card:")):
            thread_id = custom_id.split(":", 1)[1]
            cart_id = str(thread_id)
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(cart_id)
            if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
                await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
                return
            method = "pix" if custom_id.startswith("cart_pay_pix:") else "card"
            available = get_available_payment_methods() or {}
            if method not in available and not (method == "pix" and float(cart.get("total_price", 0) or 0) <= 0):
                await inter.response.send_message(
                    f"{emoji.wrong} Este método de pagamento não está configurado no momento.", ephemeral=True
                )
                return
            cart["payment_method"] = method
            cart["updated_at"] = int(datetime.utcnow().timestamp())
            loja_data.setdefault("carts", {})[cart_id] = cart
            db.save_document("loja_data", loja_data)
            try:
                await self._process_cart_continue(inter)
            except Exception as exc:
                await self._handle_cart_continue_error(inter, exc)
            return

        if custom_id.startswith("cart_back_summary:"):
            await self._restore_cart_summary(inter, custom_id.split(":", 1)[1])
            return

        # Exibe os termos sem sair do carrinho.
        if custom_id.startswith("cart_view_terms:"):
            thread_id = custom_id.split(":", 1)[1]
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(str(thread_id))
            if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
                await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
                return
            from modules.loja.preferences.utils import get_terms
            enabled, terms_text = get_terms()
            if not enabled or not terms_text:
                await inter.response.send_message(
                    f"{getattr(emoji, 'interrogation', emoji.warn)} A loja não configurou termos para esta compra.",
                    ephemeral=True,
                )
                return
            terms_embed = disnake.Embed(
                title="4M - Termos de Compra",
                description=str(terms_text)[:4000],
                color=disnake.Color.blurple(),
            )
            terms_embed.set_author(
                name=getattr(inter.user, "display_name", "Cliente"),
                icon_url=getattr(getattr(inter.user, "display_avatar", None), "url", None),
            )
            if inter.guild:
                icon_url = getattr(getattr(inter.guild, "icon", None), "url", None)
                if icon_url:
                    terms_embed.set_footer(text=inter.guild.name, icon_url=icon_url)
                else:
                    terms_embed.set_footer(text=inter.guild.name)
            await inter.response.send_message(embed=terms_embed, ephemeral=True)
            return

        # Consulta manual do pagamento, com proteção contra spam.
        if custom_id.startswith("check_payment:"):
            thread_id = custom_id.split(":", 1)[1]
            cart_id = str(thread_id)
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(cart_id)
            if not cart:
                await inter.response.send_message(f"{emoji.wrong} Pagamento não encontrado.", ephemeral=True)
                return
            if int(cart.get("user_id", 0)) != int(inter.user.id):
                await inter.response.send_message(f"{emoji.wrong} Este pagamento não pertence a você.", ephemeral=True)
                return
            if str(cart.get("status")) == "approved":
                await inter.response.send_message(f"{emoji.correct} O pagamento já foi aprovado.", ephemeral=True)
                return

            now_ts = int(datetime.utcnow().timestamp())
            last_check = int(cart.get("last_manual_check_at") or 0)
            if now_ts - last_check < 5:
                await inter.response.send_message(
                    f"{getattr(emoji, 'time', emoji.warn)} Aguarde alguns segundos antes de consultar novamente.",
                    ephemeral=True,
                )
                return
            cart["last_manual_check_at"] = now_ts
            loja_data.setdefault("carts", {})[cart_id] = cart
            db.save_document("loja_data", loja_data)
            await inter.response.defer(ephemeral=True)

            payment_data = cart.get("payment_data") or {}
            provider = payment_data.get("provider") or {}
            metadata = payment_data.get("metadata") or {}
            payment_id = (
                provider.get("payment_id") or provider.get("correlation_id")
                or provider.get("charge_id") or provider.get("txid")
            )
            payment_provider = provider.get("name")
            payment_method = metadata.get("payment_method") or cart.get("payment_method") or "pix"
            if not payment_id:
                await inter.followup.send(
                    f"{emoji.wrong} O identificador da cobrança não está disponível.", ephemeral=True
                )
                return

            from .checkout import _check_single_payment_status, _handle_payment_approved
            is_finished, final_status = await _check_single_payment_status(
                cart_id, str(payment_id), str(payment_method), payment_provider, self.bot
            )
            if is_finished and final_status == "approved":
                await _handle_payment_approved(cart_id, self.bot)
                await inter.followup.send(
                    f"{emoji.correct} Pagamento aprovado. A entrega está sendo processada.", ephemeral=True
                )
                return
            if is_finished:
                latest = db.get_document("loja_data") or {}
                latest_cart = (latest.get("carts") or {}).get(cart_id) or cart
                latest_cart["status"] = str(final_status or "failed")
                latest_cart["updated_at"] = now_ts
                latest.setdefault("carts", {})[cart_id] = latest_cart
                db.save_document("loja_data", latest)
                await inter.followup.send(
                    f"{emoji.wrong} A cobrança foi finalizada com status `{final_status}`.", ephemeral=True
                )
                return
            await inter.followup.send(
                f"{getattr(emoji, 'time', emoji.loading)} Pagamento ainda não confirmado. A verificação automática continua ativa.",
                ephemeral=True,
            )
            return

        # Handler para editar quantidade
        if custom_id.startswith("cart_edit_quantity:"):
            parts = custom_id.split(":")
            thread_id = int(parts[1])
            item_idx = int(parts[2])
            cart_id = str(thread_id)
            
            # Carregar carrinho
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            if cart.get("user_id") != inter.user.id:
                await inter.response.send_message(
                    f"{emoji.wrong} Este não é o seu carrinho!",
                    ephemeral=True
                )
                return
            
            items = cart.get("items", [])
            if item_idx >= len(items):
                await inter.response.send_message(
                    f"{emoji.wrong} Item não encontrado!",
                    ephemeral=True
                )
                return
            
            # Abrir modal para editar quantidade
            item = items[item_idx]
            current_quantity = item.get("quantity", 1)
            
            modal = self._quantity_modal(str(thread_id), item_idx, current_quantity)
            
            # Enviar modal com tratamento de erro
            try:
                if not inter.response.is_done():
                    await inter.response.send_modal(modal)
                else:
                    await inter.followup.send(
                        f"{emoji.wrong} Não foi possível abrir o modal. Tente novamente.",
                        ephemeral=True
                    )
            except disnake.errors.NotFound:
                # Interação expirou durante a criação do modal
                if not inter.response.is_done():
                    try:
                        await inter.response.send_message(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                    except:
                        pass
                else:
                    try:
                        await inter.followup.send(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                    except:
                        pass
            except Exception as e:
                # Outro erro inesperado
                if not inter.response.is_done():
                    try:
                        await inter.response.send_message(
                            f"{emoji.wrong} Ocorreu um erro inesperado: {e}",
                            ephemeral=True
                        )
                    except:
                        pass
                else:
                    try:
                        await inter.followup.send(
                            f"{emoji.wrong} Ocorreu um erro inesperado: {e}",
                            ephemeral=True
                        )
                    except:
                        pass
            return
        
        # Handler para remover item
        if custom_id.startswith("cart_remove_item:"):
            parts = custom_id.split(":")
            thread_id = int(parts[1])
            item_idx = int(parts[2])
            cart_id = str(thread_id)
            
            # Carregar carrinho
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            if cart.get("user_id") != inter.user.id:
                await inter.response.send_message(
                    f"{emoji.wrong} Este não é o seu carrinho!",
                    ephemeral=True
                )
                return
            
            items = cart.get("items", [])
            if item_idx >= len(items):
                await inter.response.send_message(
                    f"{emoji.wrong} Item não encontrado!",
                    ephemeral=True
                )
                return
            
            # Remover item
            items.pop(item_idx)
            
            if not items:
                # Carrinho vazio - deletar
                await inter.response.send_message(
                    f"{emoji.correct} Último item removido! O carrinho será deletado em breve.",
                    ephemeral=True
                )
                # Gerar e enviar transcript se habilitado (antes de deletar)
                try:
                    from modules.loja.preferences.generate_transcript import generate_cart_transcript, send_cart_transcript_to_channel
                    prefs = db.get_document("loja_preferences") or {}
                    if prefs.get("transcript_enabled", False):
                        transcript_channel_id = prefs.get("transcript_channel_id")
                        if transcript_channel_id:
                            thread = inter.guild.get_thread(thread_id)
                            if thread:
                                transcript_file = await generate_cart_transcript(thread, self.bot, cart)
                                if transcript_file:
                                    await send_cart_transcript_to_channel(self.bot, transcript_file, int(transcript_channel_id), cart)
                except Exception as e:
                    print(f"Erro ao gerar transcript: {e}")
                
                # Deletar thread e carrinho
                try:
                    thread = inter.guild.get_thread(thread_id)
                    if thread:
                        await thread.delete()
                except:
                    pass
                del loja_data["carts"][cart_id]
                db.save_document("loja_data", loja_data)
                return
            
            # Atualizar carrinho
            cart["items"] = items
            cart["total_price"] = sum(item.get("item_total", 0) for item in items)
            cart["updated_at"] = int(datetime.utcnow().timestamp())
            
            loja_data["carts"][cart_id] = cart
            db.save_document("loja_data", loja_data)
            
            # Atualizar mensagem do carrinho
            thread = inter.guild.get_thread(thread_id)
            if thread:
                mode = db.get_document("custom_mode").get("mode", "embed")
                cart_msg_id = cart.get("cart_message_id")
                if cart_msg_id:
                    try:
                        cart_msg = await thread.fetch_message(cart_msg_id)
                        # Reconstruir mensagem
                        new_cart_msg = await _build_cart_message(cart, thread, mode)
                        await cart_msg.delete()
                        cart["cart_message_id"] = new_cart_msg.id
                        loja_data["carts"][cart_id] = cart
                        db.save_document("loja_data", loja_data)
                    except:
                        pass
            
            await inter.response.send_message(
                f"{emoji.correct} Item removido do carrinho com sucesso!",
                ephemeral=True
            )
            return
    
    async def _handle_cart_continue_error(self, inter: disnake.MessageInteraction, exc: Exception):
        """Evita botão sem resposta e libera o carrinho após qualquer falha inesperada."""
        import traceback
        traceback.print_exc()
        try:
            custom_id = getattr(getattr(inter, "component", None), "custom_id", "") or ""
            thread_id = custom_id.split(":", 1)[1] if ":" in custom_id else str(getattr(inter.channel, "id", ""))
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(str(thread_id))
            if cart:
                cart["checkout_processing"] = False
                cart["checkout_error"] = str(exc)[:500]
                loja_data.setdefault("carts", {})[str(thread_id)] = cart
                db.save_document("loja_data", loja_data)
        except Exception:
            pass
        content = (
            f"{emoji.wrong} Não foi possível continuar para o pagamento.\n"
            f"{emoji.warn} Motivo: `{str(exc)[:350]}`\n"
            f"{emoji.reload} O carrinho foi liberado para uma nova tentativa."
        )
        try:
            if inter.response.is_done():
                await inter.followup.send(content, ephemeral=True)
            else:
                await inter.response.send_message(content, ephemeral=True)
        except Exception:
            pass

    async def _process_cart_continue(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(getattr(inter, "component", None), "custom_id", "") or "")
        parts = custom_id.split(":", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError("Identificador do carrinho inválido")
        thread_id = int(parts[1])
        cart_id = str(thread_id)

        # Pequena pausa para garantir que o banco foi atualizado (se houver race condition)
        await asyncio.sleep(0.1)
        
        # Carregar carrinho (recarregar do banco para garantir dados atualizados)
        loja_data = db.get_document("loja_data") or {}
        
        cart = loja_data.get("carts", {}).get(cart_id)
        
        # Se não encontrou, tentar migrar se necessário
        if not cart:
            # Tentar buscar por thread_id como int também
            cart = loja_data.get("carts", {}).get(str(thread_id))
            if not cart:
                # Tentar buscar por thread_id como int
                for key, value in loja_data.get("carts", {}).items():
                    if value.get("thread_id") == thread_id:
                        cart = value
                        cart_id = key  # Atualizar cart_id para a chave correta
                        break
        
        if not cart:
            await inter.response.send_message(
                f"{emoji.wrong} Carrinho não encontrado!",
                ephemeral=True
            )
            return
        
        # Migrar carrinho se necessário
        from .checkout import _migrate_cart_to_items
        cart = _migrate_cart_to_items(cart)
        
        # Salvar carrinho migrado se necessário
        if cart_id not in loja_data.get("carts", {}):
            loja_data["carts"][cart_id] = cart
            db.save_document("loja_data", loja_data)
        
        
        # Verificar se é o dono do carrinho
        if cart.get("user_id") != inter.user.id:
            await inter.response.send_message(
                f"{emoji.wrong} Este não é o seu carrinho!",
                ephemeral=True
            )
            return
        
        # Verificar se já está em pagamento
        if cart.get("status") != "cart":
            await inter.response.send_message(
                f"{emoji.wrong} Este carrinho já está em processo de pagamento!",
                ephemeral=True
            )
            return
        
        items = cart.get("items", [])
        if not items:
            await inter.response.send_message(
                f"{emoji.wrong} Carrinho vazio!",
                ephemeral=True
            )
            return
        
        # Verificar estoque ANTES de criar pagamento
        products = db.get_document("loja_products") or {}
        stock_errors = []
        no_stock_items = []  # Itens completamente sem estoque (para botões de notificação)
        
        for item in items:
            product_id = item.get("product_id")
            campo_id = item.get("campo_id")
            quantity = item.get("quantity", 1)
            
            if not product_id or not campo_id:
                continue
            
            product = products.get(product_id, {})
            if not product:
                continue
            
            campos = product.get("campos", {})
            campo = campos.get(campo_id, {})
            if not campo:
                continue
            
            info = product.get("info", {})
            delivery_type = info.get("delivery_type", "automatic")
            
            # Verificar se é estoque infinito
            infinite_stock = campo.get("infinite_stock", {})
            is_infinite = infinite_stock.get("enabled", False)
            
            if not is_infinite and delivery_type == "automatic":
                # Verificar estoque disponível
                stock_count = StockManager.get_available_stock(product_id, campo_id)
                
                if stock_count < quantity:
                    product_name = product.get("name", "Produto")
                    campo_name = campo.get("name", "Opção")
                    
                    if stock_count <= 0:
                        # Sem estoque - adicionar para mostrar botão de notificação
                        no_stock_items.append({
                            "product_id": product_id,
                            "campo_id": campo_id,
                            "product_name": product_name,
                            "campo_name": campo_name
                        })
                        stock_errors.append(f"**{product_name}** - `{campo_name}`: Sem estoque disponível")
                    else:
                        stock_errors.append(f"**{product_name}** - `{campo_name}`: Estoque insuficiente (disponível: {stock_count}, necessário: {quantity})")
        
        if stock_errors:
            error_msg = f"{emoji.wrong} **Estoque insuficiente para alguns produtos:**\n\n" + "\n".join(stock_errors)
            
            # Adicionar botões de notificação para produtos sem estoque
            components = []
            if no_stock_items:
                # Limitar a 5 botões (máximo por ActionRow)
                buttons = []
                for no_stock_item in no_stock_items[:5]:
                    notify_emoji = ensure_emoji(emoji.warn)
                    buttons.append(
                        disnake.ui.Button(
                            emoji=notify_emoji,
                            label=f"Notificar: {no_stock_item['product_name']}",
                            style=disnake.ButtonStyle.grey,
                            custom_id=f"notify_stock:{no_stock_item['product_id']}:{no_stock_item['campo_id']}"
                        )
                    )
                
                if buttons:
                    components.append(disnake.ui.ActionRow(*buttons))
            
            await inter.response.send_message(
                error_msg,
                components=components if components else None,
                ephemeral=True
            )
            return
        
        # Verificar se está em manutenção
        from modules.loja.preferences.utils import check_maintenance
        is_maintenance, maintenance_msg = check_maintenance(inter.user.id, inter.guild)
        if is_maintenance:
            await inter.response.send_message(
                maintenance_msg or "🔧 Sistema em manutenção. Por favor, tente novamente mais tarde.",
                ephemeral=True
            )
            return
        
        # Verificar horário de funcionamento
        from modules.loja.preferences.utils import check_store_hours
        is_open, hours_msg = check_store_hours()
        if not is_open:
            await inter.response.send_message(
                hours_msg or "⏰ A loja está fora do horário de funcionamento.",
                ephemeral=True
            )
            return
        
        # Verificar termos (se não foram aceitos ainda)
        from modules.loja.preferences.utils import get_terms
        terms_enabled, terms_text = get_terms()
        if terms_enabled and not cart.get("terms_accepted", False):
            # Mostrar modal de aceitação de termos
            # Criar modal ANTES de qualquer outra operação para evitar timeout
            from modules.loja.cart.terms_modal import TermsAcceptanceModal
            modal = TermsAcceptanceModal(cart_id)
            
            # Enviar modal imediatamente (operação rápida)
            try:
                if not inter.response.is_done():
                    await inter.response.send_modal(modal)
                else:
                    await inter.followup.send(
                        f"{emoji.wrong} Não foi possível abrir o modal. Tente novamente.",
                        ephemeral=True
                    )
            except disnake.errors.NotFound:
                # Interação expirou durante a criação do modal
                if not inter.response.is_done():
                    try:
                        await inter.response.send_message(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                    except:
                        pass
                else:
                    try:
                        await inter.followup.send(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                    except:
                        pass
            except Exception as e:
                # Outro erro inesperado
                if not inter.response.is_done():
                    try:
                        await inter.response.send_message(
                            f"{emoji.wrong} Ocorreu um erro inesperado: {e}",
                            ephemeral=True
                        )
                    except:
                        pass
                else:
                    try:
                        await inter.followup.send(
                            f"{emoji.wrong} Ocorreu um erro inesperado: {e}",
                            ephemeral=True
                        )
                    except:
                        pass
            return
        
        # Calcular total
        total_price = sum(item.get("item_total", 0) for item in items)
        payment_method = cart.get("payment_method", "pix")
        
        # Obter cupom do carrinho (se aplicado)
        discount_amount = cart.get("discount_amount", 0) or 0
        coupon_applied = cart.get("coupon_code")
        coupon_type = cart.get("coupon_type")
        is_free_purchase = cart.get("is_free_purchase", False)
        
        final_price = max(0, total_price - discount_amount)
        
        # Validar valor mínimo para pagamento PIX
        if payment_method == "pix" and final_price < 0.80:
            await inter.response.send_message(
                f"{emoji.wrong} O valor mínimo para pagamento via PIX é R$ 0,80.\n"
                f"{emoji.arrow} Valor atual: R$ {final_price:.2f}\n\n"
                f"Por favor, adicione mais itens ao carrinho ou remova o cupom.",
                ephemeral=True
            )
            return
        
        # Responder imediatamente para o botão nunca expirar.
        await inter.response.defer(ephemeral=True)
        await inter.followup.send(
            f"{emoji.loading} Quase lá! Preparando os detalhes do pagamento...", ephemeral=True
        )

        # Bloqueio contra clique duplo e cobranças duplicadas.
        latest_data = db.get_document("loja_data") or {}
        latest_cart = (latest_data.get("carts") or {}).get(cart_id) or cart
        now_ts = int(datetime.utcnow().timestamp())
        started_at = int(latest_cart.get("checkout_started_at") or 0)
        is_recent_lock = bool(latest_cart.get("checkout_processing")) and (now_ts - started_at) < 120
        if is_recent_lock:
            await inter.followup.send(
                f"{emoji.interrogation} O pagamento deste carrinho já está sendo preparado.",
                ephemeral=True,
            )
            return
        latest_cart["checkout_processing"] = True
        latest_cart["checkout_started_at"] = now_ts
        latest_data.setdefault("carts", {})[cart_id] = latest_cart
        db.save_document("loja_data", latest_data)
        cart = latest_cart

        # Criar pagamento
        try:
            # Criar descrição
            products = db.get_document("loja_products") or {}
            descriptions = []
            for item in items:
                product = products.get(item.get("product_id"))
                if product:
                    product_name = product.get("name", "Produto")
                    campos = product.get("campos", {})
                    campo = campos.get(item.get("campo_id"))
                    campo_name = campo.get("name", "") if campo else "Opção"
                    quantity = item.get("quantity", 1)
                    descriptions.append(f"{product_name} - {campo_name} x{quantity}")
            
            description = " | ".join(descriptions)
            
            # Efi Bank agora NÃO precisa de CPF e nome - API gera automaticamente
            # Criar pagamento diretamente
            
            print(f"[CART] Criando pagamento: method={payment_method}, amount={final_price}, description={description}")
            
            payment_data = await _create_payment(
                payment_method=payment_method,
                amount=final_price,
                user=inter.user,
                description=description,
                cart_id=cart_id,
            )
            
            print(f"[CART] Pagamento criado com sucesso: {payment_data.keys() if payment_data else 'None'}")
        except Exception as e:
            print(f"[CART] Erro ao criar pagamento: {e}")
            import traceback
            traceback.print_exc()
            latest_data = db.get_document("loja_data") or {}
            failed_cart = (latest_data.get("carts") or {}).get(cart_id) or cart
            failed_cart["checkout_processing"] = False
            failed_cart["checkout_error"] = str(e)[:500]
            latest_data.setdefault("carts", {})[cart_id] = failed_cart
            db.save_document("loja_data", latest_data)
            await inter.followup.send(
                content=(
                    f"{emoji.wrong} Não foi possível gerar o pagamento.\n"
                    f"{emoji.warn} Motivo: `{str(e)[:450]}`\n"
                    f"{emoji.reload} O carrinho continua aberto; corrija a configuração e tente novamente."
                ),
                ephemeral=True,
            )
            return

        # Extrair informações do pagamento
        checkout_url, copy_code = _extract_urls(payment_data or {})
        qr_bytes, qr_url = _extract_qr_image(payment_data or {})
        
        if not qr_bytes and payment_data and payment_data.get("qr_code_bytes"):
            qr_bytes = payment_data.get("qr_code_bytes")
        
        if not copy_code and payment_data:
            copy_code = payment_data.get("pix_copia_cola") or payment_data.get("copy_paste") or payment_data.get("emv")
        
        payment_ids = _extract_payment_ids(payment_data or {})
        requires_manual_approval = payment_data.get("requires_manual_approval", False) if payment_data else False
        payment_provider = payment_data.get("_provider") if payment_data else None
        
        # Se tiver URL do QR Code, tentar baixar os bytes
        if qr_url:
            base_root = _api_base_root()
            full_url = str(qr_url)
            if full_url.startswith("/"):
                full_url = base_root + full_url
            fetched = await _http_get_bytes(full_url)
            if fetched:
                qr_bytes = fetched
                qr_url = None
        
        # Obter thread
        thread = inter.guild.get_thread(thread_id) if inter.guild else None
        if thread is None and inter.guild:
            try:
                fetched = await inter.guild.fetch_channel(thread_id)
                thread = fetched if isinstance(fetched, disnake.Thread) else None
            except Exception:
                thread = None
        if not thread:
            latest_data = db.get_document("loja_data") or {}
            failed_cart = (latest_data.get("carts") or {}).get(cart_id) or cart
            failed_cart["checkout_processing"] = False
            latest_data.setdefault("carts", {})[cart_id] = failed_cart
            db.save_document("loja_data", latest_data)
            await inter.followup.send(
                f"{emoji.wrong} O canal privado do carrinho não foi encontrado.",
                ephemeral=True,
            )
            return
        
        # Formatar preços e montar um resumo completo da cobrança.
        original_price_str = _money_br(total_price)
        final_price_str = _money_br(final_price)
        discount_str = _money_br(discount_amount)
        method_names = {"pix": "PIX", "card": "Cartão de Crédito", "crypto": "Criptomoeda"}
        payment_method_display = method_names.get(payment_method, payment_method.upper())
        provider_names = {
            "sync_wallet": "Carteira Integrada",
            "mercado_pago": "Mercado Pago",
            "efibank": "Efí Bank",
            "pushinpay": "Pushin Pay",
            "misticpay": "MisticPay",
            "pix_manual": "PIX Manual",
        }
        provider_display = provider_names.get(str(payment_provider), str(payment_provider or "PIX"))

        product_preview, payment_total_units = _format_cart_products(items, products, limit=10)

        summary_lines = [f"{emoji.coin} **Subtotal:** `{original_price_str}`"]
        if discount_amount > 0:
            summary_lines.append(f"{getattr(emoji, 'receipt', emoji.coin)} **Desconto:** `-{discount_str}`")
        if coupon_applied:
            summary_lines.append(f"{getattr(emoji, 'receipt', emoji.coin)} **Cupom:** `{coupon_applied}`")
        summary_lines.extend([
            f"{emoji.pix} **Total da cobrança:** `{final_price_str}`",
            f"{getattr(emoji, 'time', emoji.calendar)} **Status:** `Aguardando pagamento`",
        ])

        components = []
        customer_buttons = []
        if copy_code:
            customer_buttons.append(
                disnake.ui.Button(
                    label="Código copia e cola",
                    emoji=ensure_emoji(getattr(emoji, "pix", "💠")),
                    style=disnake.ButtonStyle.grey,
                    custom_id=f"copy_pix:{thread_id}",
                )
            )
        customer_buttons.append(
            disnake.ui.Button(
                label="Cancelar pagamento",
                emoji=ensure_emoji(getattr(emoji, "delete", "🗑️")),
                style=disnake.ButtonStyle.danger,
                custom_id=f"cancel_checkout:{thread_id}",
            )
        )
        components.extend(_chunk_buttons(customer_buttons))
        if requires_manual_approval:
            components.append(
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Aprovar Pagamento",
                        emoji=ensure_emoji(getattr(emoji, "correct", "✅")),
                        style=disnake.ButtonStyle.success,
                        custom_id=f"approve_manual_pix:{thread_id}",
                    )
                )
            )

        files = []
        qr_attachment_url = None
        if qr_bytes:
            files.append(disnake.File(io.BytesIO(qr_bytes), filename="qrcode.png"))
            qr_attachment_url = "attachment://qrcode.png"
        elif qr_url:
            qr_attachment_url = qr_url

        product_color = None
        color_data = db.get_document("custom_colors") or {}
        primary_color = color_data.get("primary")
        if primary_color:
            try:
                product_color = disnake.Colour(int(str(primary_color).replace("#", ""), 16))
            except Exception:
                product_color = None

        safe_code = str(copy_code or "")[:3500]
        mode = (db.get_document("custom_mode") or {}).get("mode", "embed")
        brand_logo = getattr(emoji, "sales_logo", getattr(emoji, "logo", emoji.pix))
        if mode == "components":
            children = [
                disnake.ui.TextDisplay(
                    f"# {brand_logo} Pagamento PIX gerado\n"
                    f"-# <@{inter.user.id}> • Aguardando confirmação"
                ),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "Seu PIX está pronto. Escaneie o QR Code ou use o código copia e cola para pagar."
                ),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"## Produtos no carrinho • {payment_total_units} unidade(s)\n{product_preview}"
                ),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "## Resumo do pagamento\n" + "\n".join(summary_lines)
                ),
            ]
            if safe_code:
                children.extend([
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(f"## Código copia e cola\n```\n{safe_code}\n```"),
                ])
            if qr_attachment_url:
                children.extend([
                    disnake.ui.Separator(),
                    disnake.ui.MediaGallery(disnake.MediaGalleryItem(media=qr_attachment_url)),
                ])
            kwargs = {"accent_colour": product_color} if product_color else {}
            payment_container = disnake.ui.Container(*children, **kwargs)
            payment_msg = await thread.send(
                components=[payment_container] + components,
                files=files or None,
                flags=disnake.MessageFlags(is_components_v2=True),
            )
        else:
            embed = disnake.Embed(
                title=f"{brand_logo} Pagamento PIX gerado",
                description=(
                    "Seu PIX está pronto. Escaneie o QR Code ou use o código copia e cola para pagar."
                ),
                color=product_color or disnake.Color.blurple(),
            )
            try:
                embed.set_author(name=inter.user.display_name, icon_url=inter.user.display_avatar.url)
            except Exception:
                pass
            embed.add_field(
                name=f"Produtos no carrinho • {payment_total_units} unidade(s)",
                value=product_preview[:1024],
                inline=False,
            )
            embed.add_field(name="Resumo do pagamento", value="\n".join(summary_lines)[:1024], inline=False)
            if safe_code:
                embed.add_field(name="Código copia e cola", value=f"```\n{safe_code}\n```"[:1024], inline=False)
            if qr_attachment_url:
                embed.set_image(url=qr_attachment_url)
            embed.set_footer(text="Use os botões abaixo para copiar o PIX ou cancelar o pagamento.")
            embed.timestamp = datetime.utcnow()
            payment_msg = await thread.send(embed=embed, components=components, files=files or None)


        # Atualizar carrinho com dados do pagamento
        cart["status"] = "pending"
        cart["checkout_processing"] = False
        cart.pop("checkout_error", None)
        cart["message_id"] = payment_msg.id
        cart["total_price"] = final_price
        cart["discount_amount"] = discount_amount
        cart["coupon_code"] = coupon_applied
        cart["coupon_type"] = coupon_type
        cart["is_free_purchase"] = is_free_purchase
        
        # Nova estrutura organizada de payment_data
        cart["payment_data"] = {
            "local": {
                "copy_code": copy_code,
                "qr_url": qr_url,
                "qr_bytes": qr_bytes if qr_bytes else None,
                "requires_manual_approval": requires_manual_approval
            },
            "provider": {
                "name": payment_provider,
                "payment_id": payment_ids.get("payment_id") or payment_ids.get("paymentId"),
                "correlation_id": payment_ids.get("correlationID") or payment_ids.get("correlation_id"),
                "charge_id": payment_ids.get("charge_id") or payment_ids.get("id"),
                "txid": payment_ids.get("txid"),
                "raw_response": payment_data
            },
            "metadata": {
                "created_at": int(datetime.utcnow().timestamp()),
                "payment_method": payment_method,
                "amount": final_price,
                "currency": "BRL"
            }
        }
        cart["updated_at"] = int(datetime.utcnow().timestamp())
        
        loja_data["carts"][cart_id] = cart
        db.save_document("loja_data", loja_data)
        
        # Deletar mensagem antiga do carrinho
        try:
            cart_message_id = cart.get("cart_message_id")
            if cart_message_id:
                cart_msg = await thread.fetch_message(cart_message_id)
                await cart_msg.delete()
        except:
            pass
        
        # Iniciar monitoramento
        from .checkout import _monitor_payment
        if not is_free_purchase:
            asyncio.create_task(_monitor_payment(cart_id, payment_method, payment_ids, payment_provider, self.bot))
        
        await inter.followup.send(
            f"{emoji.correct} Pagamento criado! Verifique a mensagem acima.",
            ephemeral=True
        )
        return
    

    @commands.Cog.listener("on_dropdown")
    async def on_cart_add_product_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(getattr(inter, "component", None), "custom_id", "") or "")

        if custom_id.startswith("cart_manage_item:"):
            thread_id = custom_id.split(":", 1)[1]
            cart_id = str(thread_id)
            loja_data = db.get_document("loja_data") or {}
            cart = (loja_data.get("carts") or {}).get(cart_id)
            if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
                await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
                return
            if str(cart.get("status") or "cart") != "cart":
                await inter.response.send_message(
                    f"{emoji.interrogation} Este carrinho já avançou para o pagamento.", ephemeral=True
                )
                return
            try:
                item_idx = int(inter.values[0])
                item = (cart.get("items") or [])[item_idx]
            except (IndexError, TypeError, ValueError):
                await inter.response.send_message(f"{emoji.wrong} Produto inválido.", ephemeral=True)
                return

            products = db.get_document("loja_products") or {}
            product = products.get(item.get("product_id"), {}) or {}
            option = (product.get("campos") or {}).get(item.get("campo_id"), {}) or {}
            quantity = max(1, int(item.get("quantity", 1) or 1))
            total = float(item.get("item_total", 0) or 0)
            await inter.response.send_message(
                content=(
                    f"{getattr(emoji, 'cardbox', emoji.cart)} **{product.get('name', 'Produto')}**\n"
                    f"{getattr(emoji, 'settings2', emoji.config)} Opção: `{option.get('name', 'Opção')}`\n"
                    f"{emoji.cart} Quantidade: `{quantity}` • Total: `{_money_br(total)}`"
                ),
                components=[
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Editar quantidade",
                            emoji=getattr(emoji, "edit", emoji.config),
                            style=disnake.ButtonStyle.primary,
                            custom_id=f"cart_edit_quantity:{thread_id}:{item_idx}",
                        ),
                        disnake.ui.Button(
                            label="Remover produto",
                            emoji=emoji.delete,
                            style=disnake.ButtonStyle.danger,
                            custom_id=f"cart_remove_item:{thread_id}:{item_idx}",
                        ),
                    )
                ],
                ephemeral=True,
            )
            return

        if not custom_id.startswith("cart_add_product_select:"):
            return
        thread_id = custom_id.split(":", 1)[1]
        cart_id = str(thread_id)
        loja_data = db.get_document("loja_data") or {}
        cart = (loja_data.get("carts") or {}).get(cart_id)
        if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
            await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            return
        if str(cart.get("status") or "cart") != "cart":
            await inter.response.send_message(
                f"{emoji.interrogation} Este carrinho já avançou para o pagamento.", ephemeral=True
            )
            return
        try:
            product_id = str(inter.values[0])
        except (IndexError, TypeError):
            await inter.response.send_message(f"{emoji.wrong} Produto inválido.", ephemeral=True)
            return
        products = db.get_document("loja_products") or {}
        product = products.get(product_id) or {}
        if not product or not product.get("active", True):
            await inter.response.send_message(f"{emoji.wrong} Produto indisponível.", ephemeral=True)
            return
        option_choices = []
        for campo_id, campo in (product.get("campos") or {}).items():
            if not isinstance(campo, dict):
                continue
            try:
                price = float(get_effective_price(product, campo) or 0)
            except Exception:
                price = 0.0
            try:
                stock = int(StockManager.get_available_stock(product_id, campo_id) or 0)
                stock_text = "Estoque ilimitado" if stock == 999999 else f"{stock} disponível(is)"
            except Exception:
                stock_text = "Estoque verificado no pagamento"
            option_choices.append(
                disnake.SelectOption(
                    label=str(campo.get("name") or "Opção")[:100],
                    value=str(campo_id),
                    description=f"{_money_br(price)} • {stock_text}"[:100],
                    emoji=ensure_emoji(getattr(emoji, "settings2", emoji.config)),
                )
            )
            if len(option_choices) >= 25:
                break
        if not option_choices:
            await inter.response.send_message(f"{emoji.wrong} Este produto não possui opções disponíveis.", ephemeral=True)
            return
        await inter.response.send_message(
            content=(
                f"{getattr(emoji, 'cardbox', emoji.cart)} **{str(product.get('name') or 'Produto')}**\n"
                "Selecione a opção que deseja adicionar."
            ),
            components=[
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        placeholder="Escolha uma opção do produto",
                        custom_id=f"cart_add_option_select:{thread_id}:{product_id}",
                        options=option_choices,
                        min_values=1,
                        max_values=1,
                    )
                )
            ],
            ephemeral=True,
        )

    @commands.Cog.listener("on_dropdown")
    async def on_cart_add_option_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(getattr(inter, "component", None), "custom_id", "") or "")
        if not custom_id.startswith("cart_add_option_select:"):
            return
        try:
            _prefix, thread_id, product_id = custom_id.split(":", 2)
            campo_id = str(inter.values[0])
        except (ValueError, IndexError, TypeError):
            await inter.response.send_message(f"{emoji.wrong} Opção inválida.", ephemeral=True)
            return
        loja_data = db.get_document("loja_data") or {}
        cart = (loja_data.get("carts") or {}).get(str(thread_id))
        if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
            await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            return
        products = db.get_document("loja_products") or {}
        product = products.get(product_id) or {}
        campo = (product.get("campos") or {}).get(campo_id) or {}
        if not product or not campo:
            await inter.response.send_message(f"{emoji.wrong} Produto ou opção não encontrado.", ephemeral=True)
            return
        try:
            price = float(get_effective_price(product, campo) or 0)
        except Exception:
            price = 0.0
        await inter.response.send_modal(
            disnake.ui.Modal(
                title="Adicionar ao Carrinho",
                custom_id=f"cart_add_product_modal:{thread_id}:{product_id}:{campo_id}",
                components=[
                    disnake.ui.TextInput(
                        label="Quantidade",
                        placeholder="Digite a quantidade desejada",
                        custom_id="quantity",
                        style=disnake.TextInputStyle.short,
                        value="1",
                        required=True,
                        min_length=1,
                        max_length=4,
                    ),
                    disnake.ui.TextInput(
                        label="Resumo",
                        custom_id="summary",
                        style=disnake.TextInputStyle.short,
                        value=f"{str(product.get('name') or 'Produto')[:45]} • {str(campo.get('name') or 'Opção')[:35]} • {_money_br(price)}",
                        required=False,
                        max_length=100,
                    ),
                ],
            )
        )

    @commands.Cog.listener("on_dropdown")
    async def on_cart_manage_item_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(getattr(inter, "component", None), "custom_id", "") or "")
        if not custom_id.startswith("cart_manage_item:"):
            return
        thread_id = custom_id.split(":", 1)[1]
        cart_id = str(thread_id)
        loja_data = db.get_document("loja_data") or {}
        cart = (loja_data.get("carts") or {}).get(cart_id)
        if not cart:
            await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            return
        if int(cart.get("user_id", 0)) != int(inter.user.id):
            await inter.response.send_message(f"{emoji.wrong} Este não é o seu carrinho.", ephemeral=True)
            return
        try:
            item_idx = int(inter.values[0])
        except (ValueError, TypeError, IndexError):
            await inter.response.send_message(f"{emoji.wrong} Produto inválido.", ephemeral=True)
            return
        items = cart.get("items", []) or []
        if item_idx < 0 or item_idx >= len(items):
            await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
            return
        item = items[item_idx]
        products = db.get_document("loja_products") or {}
        product = products.get(item.get("product_id"), {}) or {}
        campo = (product.get("campos") or {}).get(item.get("campo_id"), {}) or {}
        product_name = str(product.get("name") or "Produto")
        option_name = str(campo.get("name") or "Opção")
        quantity = max(1, int(item.get("quantity", 1) or 1))
        item_total = float(item.get("item_total", 0) or 0)
        await inter.response.send_message(
            content=(
                f"{getattr(emoji, 'cardbox', emoji.cart)} **{product_name}**\n"
                f"{getattr(emoji, 'settings2', emoji.config)} Opção: `{option_name}`\n"
                f"{emoji.cart} Quantidade: `{quantity}`\n"
                f"{emoji.coin} Total: `{_money_br(item_total)}`"
            ),
            components=[
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Editar quantidade",
                        emoji=getattr(emoji, "edit", emoji.config),
                        style=disnake.ButtonStyle.primary,
                        custom_id=f"cart_edit_quantity:{thread_id}:{item_idx}",
                    ),
                    disnake.ui.Button(
                        label="Remover do carrinho",
                        emoji=emoji.delete,
                        style=disnake.ButtonStyle.danger,
                        custom_id=f"cart_remove_item:{thread_id}:{item_idx}",
                    ),
                )
            ],
            ephemeral=True,
        )


    @commands.Cog.listener("on_modal_submit")
    async def on_cart_add_product_modal(self, inter: disnake.ModalInteraction):
        custom_id = str(inter.custom_id or "")
        if not custom_id.startswith("cart_add_product_modal:"):
            return
        try:
            _prefix, thread_id, product_id, campo_id = custom_id.split(":", 3)
        except ValueError:
            await inter.response.send_message(f"{emoji.wrong} Dados do produto inválidos.", ephemeral=True)
            return
        if not inter.response.is_done():
            await inter.response.defer(ephemeral=True)
        try:
            quantity = int(str(inter.text_values.get("quantity", "1")).strip())
        except (ValueError, TypeError):
            quantity = 0
        if quantity < 1 or quantity > 999:
            await inter.followup.send(
                f"{emoji.wrong} Informe uma quantidade entre `1` e `999`.", ephemeral=True
            )
            return
        loja_data = db.get_document("loja_data") or {}
        cart = (loja_data.get("carts") or {}).get(str(thread_id))
        if not cart or int(cart.get("user_id", 0)) != int(inter.user.id):
            await inter.followup.send(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            return
        if str(cart.get("status") or "cart") != "cart":
            await inter.followup.send(
                f"{emoji.interrogation} Este carrinho já avançou para o pagamento.", ephemeral=True
            )
            return
        products = db.get_document("loja_products") or {}
        product = products.get(product_id) or {}
        campo = (product.get("campos") or {}).get(campo_id) or {}
        if not product or not product.get("active", True) or not campo:
            await inter.followup.send(f"{emoji.wrong} Produto ou opção indisponível.", ephemeral=True)
            return
        try:
            price = float(get_effective_price(product, campo) or 0)
        except Exception:
            price = 0.0
        updated_cart = await _add_item_to_cart(str(thread_id), product_id, campo_id, quantity, price)
        if not updated_cart:
            await inter.followup.send(
                f"{emoji.wrong} Não foi possível adicionar essa quantidade. Verifique o estoque disponível.",
                ephemeral=True,
            )
            return
        thread = inter.guild.get_thread(int(thread_id)) if inter.guild else None
        if thread is None and inter.guild:
            try:
                fetched = await inter.guild.fetch_channel(int(thread_id))
                thread = fetched if isinstance(fetched, disnake.Thread) else None
            except Exception:
                thread = None
        if thread:
            loja_data = db.get_document("loja_data") or {}
            current_cart = (loja_data.get("carts") or {}).get(str(thread_id), updated_cart)
            old_id = current_cart.get("cart_message_id")
            mode = (db.get_document("custom_mode") or {}).get("mode", "embed")
            new_message = await _build_cart_message(current_cart, thread, mode)
            current_cart["cart_message_id"] = new_message.id
            current_cart["updated_at"] = int(datetime.utcnow().timestamp())
            loja_data.setdefault("carts", {})[str(thread_id)] = current_cart
            db.save_document("loja_data", loja_data)
            if old_id:
                try:
                    old_message = await thread.fetch_message(int(old_id))
                    await old_message.delete()
                except Exception:
                    pass
        await inter.followup.send(
            f"{emoji.correct} **Produto adicionado ao mesmo carrinho.**\n"
            f"{getattr(emoji, 'cardbox', emoji.cart)} `{str(product.get('name') or 'Produto')}` • "
            f"`{str(campo.get('name') or 'Opção')}` • Quantidade `{quantity}`",
            ephemeral=True,
        )

    @commands.Cog.listener("on_modal_submit")
    async def on_edit_quantity_modal(self, inter: disnake.ModalInteraction):
        custom_id = inter.custom_id
        
        if not custom_id or not custom_id.startswith("cart_edit_quantity_modal:"):
            return
        
        # Fazer defer imediatamente para evitar timeout
        if not inter.response.is_done():
            await inter.response.defer(ephemeral=True)
        
        parts = custom_id.split(":")
        thread_id = int(parts[1])
        item_idx = int(parts[2])
        cart_id = str(thread_id)
        
        # Obter nova quantidade
        valores = inter.resolved_values
        new_quantity_str = valores.get("new_quantity", "1")
        
        try:
            new_quantity = int(new_quantity_str)
            if new_quantity < 1:
                new_quantity = 1
        except:
            await inter.followup.send(
                f"{emoji.wrong} Quantidade inválida!",
                ephemeral=True
            )
            return
        
        # Carregar carrinho
        loja_data = db.get_document("loja_data")
        cart = loja_data.get("carts", {}).get(cart_id)
        
        if not cart:
            await inter.followup.send(
                f"{emoji.wrong} Carrinho não encontrado!",
                ephemeral=True
            )
            return
        
        if cart.get("user_id") != inter.user.id:
            await inter.followup.send(
                f"{emoji.wrong} Este não é o seu carrinho!",
                ephemeral=True
            )
            return
        
        items = cart.get("items", [])
        if item_idx >= len(items):
            await inter.followup.send(
                f"{emoji.wrong} Item não encontrado!",
                ephemeral=True
            )
            return
        
        # Atualizar quantidade - validar estoque primeiro
        item = items[item_idx]
        product_id = item.get("product_id")
        campo_id = item.get("campo_id")
        
        # Validar estoque disponível
        from .stock_manager import StockManager
        products = db.get_document("loja_products")
        product = products.get(product_id, {})
        campo = product.get("campos", {}).get(campo_id, {})
        
        # Verificar se é estoque infinito
        infinite_stock = campo.get("infinite_stock", {})
        is_infinite = infinite_stock.get("enabled", False)
        
        if not is_infinite:
            # Verificar estoque disponível
            stock_count = StockManager.get_available_stock(product_id, campo_id)
            
            # Calcular quantidade total já no carrinho (excluindo o item atual)
            total_quantity_in_cart = sum(
                it.get("quantity", 0) for idx, it in enumerate(items) 
                if idx != item_idx and it.get("product_id") == product_id and it.get("campo_id") == campo_id
            )
            
            # Estoque disponível considerando outros itens no carrinho
            available_stock = stock_count - total_quantity_in_cart
            
            if new_quantity > available_stock:
                await inter.followup.send(
                    f"{emoji.wrong} Quantidade inválida! Estoque disponível: `{available_stock}`",
                    ephemeral=True
                )
                return
        
        # Atualizar quantidade
        item["quantity"] = new_quantity
        item["item_total"] = item.get("price_per_unit", 0) * new_quantity
        
        cart["items"] = items
        cart["total_price"] = sum(item.get("item_total", 0) for item in items)
        cart["updated_at"] = int(datetime.utcnow().timestamp())
        
        loja_data["carts"][cart_id] = cart
        db.save_document("loja_data", loja_data)
        
        # Atualizar mensagem do carrinho
        thread = inter.guild.get_thread(thread_id)
        if thread:
            mode = db.get_document("custom_mode").get("mode", "embed")
            cart_msg_id = cart.get("cart_message_id")
            if cart_msg_id:
                try:
                    cart_msg = await thread.fetch_message(cart_msg_id)
                    # Reconstruir mensagem
                    new_cart_msg = await _build_cart_message(cart, thread, mode)
                    await cart_msg.delete()
                    cart["cart_message_id"] = new_cart_msg.id
                    loja_data["carts"][cart_id] = cart
                    db.save_document("loja_data", loja_data)
                except:
                    pass
        
        await inter.followup.send(
            f"{emoji.correct} Quantidade atualizada com sucesso!",
            ephemeral=True
        )
    
    @commands.Cog.listener("on_button_click")
    async def on_coupon_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Handler para aplicar cupom
        if custom_id.startswith("cart_apply_coupon:"):
            thread_id = int(custom_id.split(":")[1])
            cart_id = str(thread_id)
            
            # Criar modal primeiro (operação rápida)
            modal = disnake.ui.Modal(
                title="Usar Cupom de Desconto",
                custom_id=f"cart_coupon_modal:{thread_id}",
                components=[
                    disnake.ui.TextInput(
                        label="NOME DO CUPOM",
                        placeholder="Coloque o nome do cupom",
                        custom_id="coupon_code",
                        style=disnake.TextInputStyle.short,
                        required=True,
                        max_length=30
                    )
                ]
            )
            
            # Tentar abrir modal imediatamente
            try:
                if not inter.response.is_done():
                    await inter.response.send_modal(modal)
                else:
                    # Se já foi respondida, não podemos enviar modal
                    await inter.followup.send(
                        f"{emoji.wrong} Não foi possível abrir o modal. Tente novamente.",
                        ephemeral=True
                    )
            except disnake.errors.NotFound:
                # Interação expirou - tentar enviar mensagem de erro
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                    else:
                        await inter.followup.send(
                            f"{emoji.wrong} A interação expirou. Por favor, tente novamente.",
                            ephemeral=True
                        )
                except:
                    pass
            except Exception as e:
                # Outro erro - tentar enviar mensagem de erro
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            f"{emoji.wrong} Erro ao abrir modal: {str(e)}",
                            ephemeral=True
                        )
                    else:
                        await inter.followup.send(
                            f"{emoji.wrong} Erro ao abrir modal: {str(e)}",
                            ephemeral=True
                        )
                except:
                    pass
            return
        
        # Handler para remover cupom
        if custom_id.startswith("cart_remove_coupon:"):
            thread_id = int(custom_id.split(":")[1])
            cart_id = str(thread_id)
            
            # Carregar carrinho
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            if cart.get("user_id") != inter.user.id:
                await inter.response.send_message(
                    f"{emoji.wrong} Este não é o seu carrinho!",
                    ephemeral=True
                )
                return
            
            # Remover cupom
            cart["coupon_code"] = None
            cart["coupon_type"] = None
            cart["discount_amount"] = 0
            cart["is_free_purchase"] = False
            cart["updated_at"] = int(datetime.utcnow().timestamp())
            
            loja_data["carts"][cart_id] = cart
            db.save_document("loja_data", loja_data)
            
            # Atualizar mensagem do carrinho
            thread = inter.guild.get_thread(thread_id)
            if thread:
                mode = db.get_document("custom_mode").get("mode", "embed")
                cart_msg_id = cart.get("cart_message_id")
                if cart_msg_id:
                    try:
                        cart_msg = await thread.fetch_message(cart_msg_id)
                        # Reconstruir mensagem
                        new_cart_msg = await _build_cart_message(cart, thread, mode)
                        await cart_msg.delete()
                        cart["cart_message_id"] = new_cart_msg.id
                        loja_data["carts"][cart_id] = cart
                        db.save_document("loja_data", loja_data)
                    except:
                        pass
            
            await inter.response.send_message(
                f"{emoji.correct} Cupom removido com sucesso!",
                ephemeral=True
            )
            return
    
    @commands.Cog.listener("on_modal_submit")
    async def on_coupon_modal(self, inter: disnake.ModalInteraction):
        custom_id = inter.custom_id
        
        if not custom_id or not custom_id.startswith("cart_coupon_modal:"):
            return
        
        # Fazer defer imediatamente para evitar timeout
        if not inter.response.is_done():
            await inter.response.defer(ephemeral=True)
        
        thread_id = int(custom_id.split(":")[1])
        cart_id = str(thread_id)
        
        # Obter código do cupom
        valores = inter.resolved_values
        coupon_code = valores.get("coupon_code", "").strip().upper()
        
        if not coupon_code:
            await inter.followup.send(
                f"{emoji.wrong} Código do cupom não pode estar vazio!",
                ephemeral=True
            )
            return
        
        # Carregar carrinho
        loja_data = db.get_document("loja_data")
        cart = loja_data.get("carts", {}).get(cart_id)
        
        if not cart:
            await inter.followup.send(
                f"{emoji.wrong} Carrinho não encontrado!",
                ephemeral=True
            )
            return
        
        if cart.get("user_id") != inter.user.id:
            await inter.followup.send(
                f"{emoji.wrong} Este não é o seu carrinho!",
                ephemeral=True
            )
            return
        
        items = cart.get("items", [])
        if not items:
            await inter.followup.send(
                f"{emoji.wrong} Carrinho vazio!",
                ephemeral=True
            )
            return
        
        # Calcular total do carrinho
        total_price = sum(item.get("item_total", 0) for item in items)
        
        # Validar cupom (tentar com o primeiro produto do carrinho)
        products = db.get_document("loja_products")
        first_item = items[0]
        first_product_id = first_item.get("product_id")
        
        is_valid, error_msg, discount, ctype, coupon_data = CouponValidator.validate_coupon(
            coupon_code,
            first_product_id,
            inter.user.id,
            total_price,
            inter.guild
        )
        
        if not is_valid:
            # O mesmo campo aceita um código de indicação, sem criar comando extra.
            from modules.loja.referrals.manager import ReferralManager
            ref_valid, ref_error, ref_discount, _ref_data = ReferralManager.validate(
                coupon_code, inter.user.id, total_price
            )
            if not ref_valid:
                await inter.followup.send(
                    f"{emoji.wrong} Código inválido: {ref_error or error_msg}",
                    ephemeral=True,
                )
                return
            is_valid = True
            discount = ref_discount
            ctype = "referral"
            cart["referral_code"] = coupon_code
            ReferralManager.register_pending(coupon_code, inter.user.id, cart_id)
        else:
            cart.pop("referral_code", None)
        
        # Aplicar cupom ou indicação
        cart["coupon_code"] = coupon_code
        cart["coupon_type"] = ctype
        cart["discount_amount"] = discount
        cart["is_free_purchase"] = CouponValidator.is_free_coupon(discount, total_price)
        cart["updated_at"] = int(datetime.utcnow().timestamp())
        
        loja_data["carts"][cart_id] = cart
        db.save_document("loja_data", loja_data)
        
        # Atualizar mensagem do carrinho
        thread = inter.guild.get_thread(thread_id)
        if thread:
            mode = db.get_document("custom_mode").get("mode", "embed")
            cart_msg_id = cart.get("cart_message_id")
            if cart_msg_id:
                try:
                    cart_msg = await thread.fetch_message(cart_msg_id)
                    # Reconstruir mensagem
                    new_cart_msg = await _build_cart_message(cart, thread, mode)
                    await cart_msg.delete()
                    cart["cart_message_id"] = new_cart_msg.id
                    loja_data["carts"][cart_id] = cart
                    db.save_document("loja_data", loja_data)
                except:
                    pass
        
        discount_str = f"R$ {discount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        await inter.followup.send(
            f"{emoji.correct} Código `{coupon_code}` aplicado com sucesso. Desconto: `{discount_str}`",
            ephemeral=True
        )
    
    @commands.Cog.listener("on_button_click")
    async def on_balance_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Handler para usar saldo no carrinho
        if custom_id.startswith("cart_use_balance:"):
            thread_id = int(custom_id.split(":")[1])
            cart_id = str(thread_id)
            
            # Verificar se sistema de saldo está habilitado
            saldo_config = db.get_document("loja_saldo_config") or {}
            if not saldo_config.get("enabled", False):
                await inter.response.send_message(
                    f"{emoji.wrong} O sistema de saldo está desabilitado.",
                    ephemeral=True
                )
                return
            
            # Obter saldo do usuário
            from modules.loja.saldo.balance_manager import BalanceManager
            user_balance = BalanceManager.get_user_balance(inter.user.id)
            
            if user_balance <= 0:
                await inter.response.send_message(
                    f"{emoji.wrong} Você não possui saldo disponível.",
                    ephemeral=True
                )
                return
            
            # Carregar carrinho
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            if cart.get("user_id") != inter.user.id:
                await inter.response.send_message(
                    f"{emoji.wrong} Este não é o seu carrinho!",
                    ephemeral=True
                )
                return
            
            # Calcular total do carrinho
            items = cart.get("items", [])
            total_price = sum(item.get("item_total", 0) for item in items)
            discount_amount = cart.get("discount_amount", 0) or 0
            final_price = max(0, total_price - discount_amount)
            
            # Criar select menu com opções
            await inter.response.send_message(
                f"{emoji.wallet} **Seu saldo:** R$ {user_balance:.2f}\n"
                f"{emoji.cart} **Valor do carrinho:** R$ {final_price:.2f}\n\n"
                f"Selecione como deseja usar o saldo:",
                components=[
                    disnake.ui.ActionRow(
                        disnake.ui.StringSelect(
                            placeholder="Escolha uma opção",
                            custom_id=f"balance_action:{cart_id}",
                            options=[
                                disnake.SelectOption(
                                    label="Pagar totalmente com saldo",
                                    value="pay_full",
                                    description=f"Usar R$ {min(user_balance, final_price):.2f} do saldo",
                                    emoji=emoji.dollar if hasattr(emoji, "dollar") else "💵"
                                ),
                                disnake.SelectOption(
                                    label="Usar saldo parcialmente",
                                    value="pay_partial",
                                    description="Escolher quanto usar do saldo",
                                    emoji=emoji.wallet if hasattr(emoji, "wallet") else "💰"
                                )
                            ]
                        )
                    )
                ],
                ephemeral=True
            )
    
    @commands.Cog.listener("on_dropdown")
    async def on_balance_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Handler para ações de saldo
        if custom_id.startswith("balance_action:"):
            cart_id = custom_id.split(":")[1]
            
            if not inter.values:
                await inter.response.send_message(
                    f"{emoji.wrong} Nenhuma opção selecionada.",
                    ephemeral=True
                )
                return
            
            action = inter.values[0]
            
            # Carregar carrinho
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            if cart.get("user_id") != inter.user.id:
                await inter.response.send_message(
                    f"{emoji.wrong} Este não é o seu carrinho!",
                    ephemeral=True
                )
                return
            
            # Obter saldo do usuário
            from modules.loja.saldo.balance_manager import BalanceManager
            user_balance = BalanceManager.get_user_balance(inter.user.id)
            
            # Calcular total do carrinho
            items = cart.get("items", [])
            total_price = sum(item.get("item_total", 0) for item in items)
            discount_amount = cart.get("discount_amount", 0) or 0
            final_price = max(0, total_price - discount_amount)
            
            # Pagar totalmente com saldo
            if action == "pay_full":
                if user_balance < final_price:
                    await inter.response.send_message(
                        f"{emoji.wrong} Saldo insuficiente! Necessário: R$ {final_price:.2f}, Disponível: R$ {user_balance:.2f}",
                        ephemeral=True
                    )
                    return
                
                # Usar saldo
                success, message = BalanceManager.use_balance(
                    inter.user.id,
                    final_price,
                    reference_id=cart_id,
                    description="Pagamento de carrinho com saldo"
                )
                
                if not success:
                    await inter.response.send_message(
                        f"{emoji.wrong} Erro ao usar saldo: {message}",
                        ephemeral=True
                    )
                    return
                
                # Marcar carrinho como pago com saldo
                cart["status"] = "paid_with_balance"
                cart["balance_applied"] = final_price
                cart["payment_method"] = "balance"
                cart["total_price"] = 0
                loja_data["carts"][cart_id] = cart
                db.save_document("loja_data", loja_data)
                
                # Defer para processar a entrega
                await inter.response.defer(ephemeral=True)
                
                # Deletar mensagem do carrinho
                thread_id = cart.get("thread_id")
                thread = inter.guild.get_thread(thread_id) if thread_id else None
                if thread:
                    cart_msg_id = cart.get("cart_message_id")
                    if cart_msg_id:
                        try:
                            cart_msg = await thread.fetch_message(cart_msg_id)
                            await cart_msg.delete()
                        except Exception:
                            pass
                
                # Processar entrega de produtos
                from .delivery import process_automatic_delivery
                
                # Entregar cada item do carrinho
                items = cart.get("items", [])
                products = db.get_document("loja_products")
                
                for item in items:
                    product_id = item.get("product_id")
                    campo_id = item.get("campo_id")
                    quantity = item.get("quantity", 1)
                    
                    product = products.get(product_id, {})
                    product_name = product.get("name", "Produto")
                    campos = product.get("campos", {})
                    campo = campos.get(campo_id, {})
                    campo_name = campo.get("name", "Opção")
                    
                    # Entregar produto
                    await process_automatic_delivery(
                        inter.user,
                        product_id,
                        campo_id,
                        product_name,
                        campo_name,
                        quantity,
                        thread=thread,
                        guild=inter.guild
                    )
                
                # Aplicar cashback ao saldo do usuário
                try:
                    from modules.loja.cashback.manager import CashbackManager
                    if CashbackManager.is_enabled():
                        # Calcular cashback baseado no valor pago com saldo
                        user_roles = []
                        if isinstance(inter.user, disnake.Member):
                            user_roles = [role.id for role in inter.user.roles]
                        
                        cashback_amount = CashbackManager.calculate_cashback(final_price, user_roles)
                        if cashback_amount > 0:
                            success, message = CashbackManager.apply_cashback(
                                inter.user.id,
                                cashback_amount,
                                purchase_ref=cart_id
                            )
                            if success:
                                print(f"[BALANCE_CHECKOUT] Cashback de R$ {cashback_amount:.2f} creditado ao usuário {inter.user.id}")
                except Exception as e:
                    print(f"[BALANCE_CHECKOUT] Erro ao processar cashback: {e}")
                
                # Deletar thread após entrega
                if thread:
                    try:
                        await thread.delete()
                        print(f"[BALANCE_CHECKOUT] Thread {thread_id} deletada após pagamento com saldo")
                    except Exception as e:
                        print(f"[BALANCE_CHECKOUT] Erro ao deletar thread: {e}")
                
                await inter.followup.send(
                    f"{emoji.correct} Pagamento realizado com saldo! Produtos entregues.",
                    ephemeral=True
                )
            
            # Usar saldo parcialmente
            elif action == "pay_partial":
                # Abrir modal para pedir valor
                modal = disnake.ui.Modal(
                    title="Usar Saldo Parcialmente",
                    custom_id=f"partial_balance_modal:{cart_id}",
                    components=[
                        disnake.ui.TextInput(
                            label=f"Quanto usar do saldo? (máx: R$ {min(user_balance, final_price):.2f})",
                            placeholder="Ex: 50.00",
                            custom_id="amount",
                            required=True,
                            max_length=10
                        )
                    ]
                )
                await inter.response.send_modal(modal)
    
    @commands.Cog.listener("on_modal_submit")
    async def on_partial_balance_modal(self, inter: disnake.ModalInteraction):
        custom_id = inter.custom_id
        
        # Modal de saldo parcial
        if custom_id.startswith("partial_balance_modal:"):
            cart_id = custom_id.split(":")[1]
            
            try:
                amount = float(inter.text_values["amount"].replace(",", "."))
                
                if amount <= 0:
                    await inter.response.send_message(
                        f"{emoji.wrong} O valor deve ser maior que zero.",
                        ephemeral=True
                    )
                    return
                
                # Carregar carrinho
                loja_data = db.get_document("loja_data")
                cart = loja_data.get("carts", {}).get(cart_id)
                
                if not cart:
                    await inter.response.send_message(
                        f"{emoji.wrong} Carrinho não encontrado!",
                        ephemeral=True
                    )
                    return
                
                # Obter saldo
                from modules.loja.saldo.balance_manager import BalanceManager
                user_balance = BalanceManager.get_user_balance(inter.user.id)
                
                # Calcular total
                items = cart.get("items", [])
                total_price = sum(item.get("item_total", 0) for item in items)
                discount_amount = cart.get("discount_amount", 0) or 0
                final_price = max(0, total_price - discount_amount)
                
                # Validar valores
                if amount > user_balance:
                    await inter.response.send_message(
                        f"{emoji.wrong} Saldo insuficiente! Disponível: R$ {user_balance:.2f}",
                        ephemeral=True
                    )
                    return
                
                if amount > final_price:
                    await inter.response.send_message(
                        f"{emoji.wrong} Valor maior que o total do carrinho (R$ {final_price:.2f})!",
                        ephemeral=True
                    )
                    return
                
                # Aplicar desconto de saldo
                cart["discount_amount"] = (discount_amount or 0) + amount
                cart["balance_to_use"] = amount  # Marcar para usar no checkout
                loja_data["carts"][cart_id] = cart
                db.save_document("loja_data", loja_data)
                
                await inter.response.send_message(
                    f"{emoji.correct} R$ {amount:.2f} do saldo será usado no pagamento!",
                    ephemeral=True
                )
                
                # Atualizar mensagem do carrinho
                thread_id = cart.get("thread_id")
                thread = inter.guild.get_thread(thread_id) if thread_id else None
                if thread:
                    mode = db.get_document("custom_mode").get("mode", "embed")
                    from .checkout import _build_cart_message
                    cart_msg_id = cart.get("cart_message_id")
                    if cart_msg_id:
                        try:
                            cart_msg = await thread.fetch_message(cart_msg_id)
                            new_cart_msg = await _build_cart_message(cart, thread, mode)
                            await cart_msg.delete()
                            cart["cart_message_id"] = new_cart_msg.id
                            loja_data["carts"][cart_id] = cart
                            db.save_document("loja_data", loja_data)
                        except Exception:
                            pass
            except ValueError:
                await inter.response.send_message(
                    f"{emoji.wrong} Valor inválido. Use apenas números.",
                    ephemeral=True
                )
            except Exception as e:
                await inter.response.send_message(
                    f"{emoji.wrong} Erro: {str(e)}",
                    ephemeral=True
                )


def setup(bot: commands.Bot):
    bot.add_cog(CartButtonHandlers(bot))

