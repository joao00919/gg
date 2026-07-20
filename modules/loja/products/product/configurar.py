from disnake.ext import commands
import disnake

from functions.emoji import emoji
from functions.message import message, embed_message
from functions.database import database as db
from functions.utils import utils
from functions.text_utils import wrap_text
from functions.loja_products import get_product_description

class ConfigurarProduto(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _format_price_brl(value: float) -> str:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _build_legacy_embed(product: dict, guild: disnake.Guild, formatted_desc: bool = True) -> disnake.Embed:
        name = product.get("name", "Produto")
        info = product.get("info") or {}
        desc = get_product_description(product)
        hex_color = info.get("hex_color")
        banner = info.get("banner")
        campos = product.get("campos") or {}
        
        # Obter preferências de exibição (com valores padrão para produtos antigos)
        display_prefs = info.get("display_preferences", {})
        if not display_prefs:
            # Inicializar preferências padrão se não existirem
            display_prefs = {
                "show_sales": True,
                "show_options": True,
                "show_stock": True
            }
            info["display_preferences"] = display_prefs
        show_sales = display_prefs.get("show_sales", True)
        show_options = display_prefs.get("show_options", True)
        
        prices = [campo.get("price", 0) for campo in campos.values()]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        if min_price == max_price:
            price_text = ConfigurarProduto._format_price_brl(min_price)
        else:
            price_text = f"{ConfigurarProduto._format_price_brl(min_price)} - {ConfigurarProduto._format_price_brl(max_price)}"

        embed_kwargs = {}
        if hex_color:
            try:
                embed_kwargs["color"] = int(hex_color.replace("#", ""), 16)
            except:
                pass

        # Aplicar quebra de linha se formatada
        if formatted_desc and desc:
            desc = wrap_text(desc, max_line_length=50)

        embed = disnake.Embed(title=name, description=desc if desc else None, **embed_kwargs)
        embed.add_field(name=f"{emoji.dollar} Preço", value=f"`{price_text}`", inline=True)
        
        # Adicionar opções primeiro (se habilitado)
        if show_options:
            options_count = len(campos)
            embed.add_field(
                name=f"{emoji.information} Opções",
                value=f"`{options_count} disponível`" if options_count == 1 else f"`{options_count} disponíveis`",
                inline=True,
            )
        
        # Adicionar vendas depois (se habilitado)
        if show_sales:
            purchases_count = len(info.get("purchasesIds", []))
            if purchases_count > 0:
                embed.add_field(
                    name=f"{emoji.dollar} Vendas",
                    value=f"`{purchases_count} {'venda realizada' if purchases_count == 1 else 'vendas realizadas'}`",
                    inline=True
                )
        
        if banner:
            embed.set_image(url=banner)
        icon_url = guild.icon.url if guild.icon else None
        embed.set_footer(text=guild.name, icon_url=icon_url)
        embed.timestamp = disnake.utils.utcnow()
        return embed

    @staticmethod
    def _build_container_components(product: dict, image_inside: bool, product_id: str, formatted_desc: bool = True) -> list:
        info = product.get("info") or {}
        name = product.get("name", "Produto")
        desc = get_product_description(product)
        hex_color = info.get("hex_color")
        banner = info.get("banner")
        campos = product.get("campos") or {}
        
        # Obter preferências de exibição (com valores padrão para produtos antigos)
        display_prefs = info.get("display_preferences", {})
        if not display_prefs:
            # Inicializar preferências padrão se não existirem
            display_prefs = {
                "show_sales": True,
                "show_options": True,
                "show_stock": True
            }
            info["display_preferences"] = display_prefs
        show_sales = display_prefs.get("show_sales", True)
        show_options = display_prefs.get("show_options", True)
        
        # Obter configuração do botão
        button_config = info.get("buy_button", {})
        if not button_config:
            # Inicializar botão padrão se não existir
            button_config = {
                "label": "Comprar",
                "emoji": emoji.cart
            }
            info["buy_button"] = button_config
        button_label = button_config.get("label", "Comprar")
        button_emoji_str = button_config.get("emoji", emoji.cart)

        prices = [campo.get("price", 0) for campo in campos.values()]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        if min_price == max_price:
            price_text = ConfigurarProduto._format_price_brl(min_price)
        else:
            price_text = f"{ConfigurarProduto._format_price_brl(min_price)} - {ConfigurarProduto._format_price_brl(max_price)}"

        components = []
        container_kwargs = {}
        if hex_color:
            try:
                container_kwargs["accent_colour"] = disnake.Colour(int(hex_color.replace("#", ""), 16))
            except:
                pass

        title_text = f"**{name}**"
        # Sempre adicionar descrição se existir
        if desc:
            if formatted_desc:
                # Quebrar linha automaticamente
                desc = wrap_text(desc, max_line_length=50)
            title_text += f"\n{desc}"

        # Construir informações de preço
        price_info_parts = [f"**{price_text}**"]
        
        # Adicionar opções primeiro (se habilitado)
        if show_options:
            price_info_parts.append(f"-# {len(campos)} {'opção' if len(campos) == 1 else 'opções'} {'disponível' if len(campos) == 1 else 'disponíveis'}")
        
        # Adicionar vendas depois (se habilitado)
        if show_sales:
            purchases_count = len(info.get("purchasesIds", []))
            if purchases_count > 0:
                price_info_parts.append(f"-# {purchases_count} {'venda realizada' if purchases_count == 1 else 'vendas realizadas'}")
        
        price_info_text = "\n".join(price_info_parts)

        inner_items = []
        if image_inside and banner:
            inner_items.append(disnake.ui.MediaGallery(disnake.MediaGalleryItem(media=banner)))
        inner_items.append(disnake.ui.TextDisplay(title_text))
        
        inner_items.append(disnake.ui.Separator())
        
        # Criar botão com emoji customizado
        btn_emoji = button_emoji_str
        if isinstance(btn_emoji, str) and btn_emoji.startswith("<"):
            try:
                btn_emoji = disnake.PartialEmoji.from_str(btn_emoji)
            except:
                btn_emoji = emoji.cart
        elif not btn_emoji:
            btn_emoji = emoji.cart
        
        # Criar Section com texto de preço
        inner_items.append(
            disnake.ui.Section(
                disnake.ui.TextDisplay(price_info_text),
                accessory=disnake.ui.Button(
                    label=button_label,
                    emoji=btn_emoji,
                    style=disnake.ButtonStyle.grey,
                    custom_id=f"buy_product:{product_id}"
                )
            )
        )
        

        container = disnake.ui.Container(*inner_items, **container_kwargs)
        if (not image_inside) and banner:
            components.append(disnake.ui.MediaGallery(disnake.MediaGalleryItem(media=banner)))
        components.append(container)
        return components

    @staticmethod
    def panel(inter: disnake.MessageInteraction, product_id: str):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            return ConfigurarProduto._panel_embed(inter, product_id)
        return ConfigurarProduto._panel_components(inter, product_id)

    @staticmethod
    def _panel_components(inter: disnake.MessageInteraction, product_id: str) -> dict:
        products = db.get_document("loja_products") or {}
        product = products.get(product_id) or {}
        info = product.get("info") or {}
        campos = product.get("campos") or {}

        name = str(product.get("name") or "Produto sem nome")[:100]
        description = get_product_description(product)
        delivery = "Manual" if str(info.get("delivery_type") or "automatic") == "manual" else "Automático"

        prices: list[float] = []
        stock_total = 0
        first_field = None
        for field in campos.values():
            if not isinstance(field, dict):
                continue
            if first_field is None:
                first_field = field
            try:
                prices.append(float(field.get("price", 0) or 0))
            except (TypeError, ValueError):
                pass
            stock = field.get("stock", field.get("estoque", []))
            if isinstance(stock, (list, tuple, set, dict)):
                stock_total += len(stock)
            elif isinstance(stock, (int, float)):
                stock_total += max(0, int(stock))

        price = min(prices) if prices else 0.0
        price_text = ConfigurarProduto._format_price_brl(price)
        field = first_field or {}
        conditions = field.get("condicoes") or {}
        roles = field.get("cargos") or {}
        authorized = roles.get("authorized") or roles.get("autorizados") or []
        authorized_text = "Todos Cargos" if not authorized else f"{len(authorized)} cargo(s)"

        def val(key: str) -> str:
            value = conditions.get(key)
            return "-" if value in (None, "", 0, 0.0) else str(value)

        text = (
            f"# {getattr(emoji, 'sales_logo', getattr(emoji, 'zenyx2', emoji.z0))}\n"
            f"-# Painel > Loja > Produtos > **{name}**\n\n"
            "## Informações do Produto\n"
            f"Nome: `{name}` | Preço: `{price_text}`\n"
            f"Estoque: `{stock_total} Unidades` | Estilo da Entrega: `{delivery}`\n"
            "Descrição:\n"
            f"```\n{description[:1400]}\n```\n"
            "## Condições atuais\n"
            f"Valor mínimo: `{val('valorMin')}`\n"
            f"Valor máximo: `{val('valorMax')}`\n"
            f"Quantidade mínima: `{val('quantidadeMin')}`\n"
            f"Quantidade máxima: `{val('quantidadeMax')}`\n"
            f"Cargos autorizados a comprar: `{authorized_text}`"
        )

        color_data = db.get_document("custom_colors") or {}
        container_kwargs = {}
        raw_color = info.get("hex_color") or color_data.get("primary")
        if raw_color:
            try:
                container_kwargs["accent_colour"] = disnake.Colour(int(str(raw_color).replace("#", ""), 16))
            except (TypeError, ValueError):
                pass

        return {"components": [
            disnake.ui.Container(
                disnake.ui.TextDisplay(text),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Editar", emoji=emoji.edit, custom_id=f"Loja_EditarProduto_Basico:{product_id}"),
                    disnake.ui.Button(label="Estoque", emoji=emoji.cardbox, custom_id=f"Loja_CamposProduto:{product_id}"),
                    disnake.ui.Button(label="Estilo de Entrega", emoji=getattr(emoji, "information", emoji.config), custom_id=f"Loja_ProdutoDelivery:{product_id}"),
                    disnake.ui.Button(label="Config.Extra", emoji=emoji.config, custom_id=f"Loja_EditarProduto_Preferencias:{product_id}"),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Configurações", emoji=emoji.config, custom_id=f"Loja_EditarProduto:{product_id}"),
                    disnake.ui.Button(label="Sincronizar", emoji=emoji.reload, custom_id=f"Loja_AtualizarProduto:{product_id}"),
                    disnake.ui.Button(label="Deletar", emoji=emoji.delete, custom_id=f"Loja_ApagarProduto:{product_id}"),
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Loja_Produtos")
            ),
        ]}

    @staticmethod
    def _panel_embed(inter: disnake.MessageInteraction, product_id: str) -> dict:
        products = db.get_document("loja_products") or {}
        product = products.get(product_id) or {}
        info = product.get("info") or {}
        campos = product.get("campos") or {}
        name = str(product.get("name") or "Produto sem nome")[:100]
        description = get_product_description(product)
        delivery = "Manual" if str(info.get("delivery_type") or "automatic") == "manual" else "Automático"
        prices: list[float] = []
        stock_total = 0
        first_field = None
        for field in campos.values():
            if not isinstance(field, dict):
                continue
            first_field = first_field or field
            try:
                prices.append(float(field.get("price", 0) or 0))
            except (TypeError, ValueError):
                pass
            stock = field.get("stock", field.get("estoque", []))
            if isinstance(stock, (list, tuple, set, dict)):
                stock_total += len(stock)
            elif isinstance(stock, (int, float)):
                stock_total += max(0, int(stock))
        price_text = ConfigurarProduto._format_price_brl(min(prices) if prices else 0.0)
        conditions = (first_field or {}).get("condicoes") or {}
        authorized = ((first_field or {}).get("cargos") or {}).get("authorized") or []

        def val(key: str) -> str:
            value = conditions.get(key)
            return "-" if value in (None, "", 0, 0.0) else str(value)

        embed = disnake.Embed(
            title=f"{getattr(emoji, 'sales_logo', getattr(emoji, 'zenyx2', emoji.z0))} {name}",
            description=(
                f"-# Painel > Loja > Produtos > **{name}**\n\n"
                "**Informações do Produto**\n"
                f"Nome: `{name}` | Preço: `{price_text}`\n"
                f"Estoque: `{stock_total} Unidades` | Estilo da Entrega: `{delivery}`\n\n"
                f"**Descrição**\n```\n{description[:1200]}\n```\n"
                "**Condições atuais**\n"
                f"Valor mínimo: `{val('valorMin')}`\n"
                f"Valor máximo: `{val('valorMax')}`\n"
                f"Quantidade mínima: `{val('quantidadeMin')}`\n"
                f"Quantidade máxima: `{val('quantidadeMax')}`\n"
                f"Cargos autorizados a comprar: `{'Todos Cargos' if not authorized else str(len(authorized)) + ' cargo(s)'}`"
            ),
        )
        return {"embed": embed, "components": [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Editar", emoji=emoji.edit, custom_id=f"Loja_EditarProduto_Basico:{product_id}"),
                disnake.ui.Button(label="Estoque", emoji=emoji.cardbox, custom_id=f"Loja_CamposProduto:{product_id}"),
                disnake.ui.Button(label="Estilo de Entrega", emoji=getattr(emoji, "information", emoji.config), custom_id=f"Loja_ProdutoDelivery:{product_id}"),
                disnake.ui.Button(label="Config.Extra", emoji=emoji.config, custom_id=f"Loja_EditarProduto_Preferencias:{product_id}"),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Configurações", emoji=emoji.config, custom_id=f"Loja_EditarProduto:{product_id}"),
                disnake.ui.Button(label="Sincronizar", emoji=emoji.reload, custom_id=f"Loja_AtualizarProduto:{product_id}"),
                disnake.ui.Button(label="Deletar", emoji=emoji.delete, custom_id=f"Loja_ApagarProduto:{product_id}"),
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id="Loja_Produtos")),
        ]}

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        custom_id = str(inter.component.custom_id or "")
        if custom_id.startswith("Loja_ProdutoDelivery:"):
            product_id = custom_id.split(":", 1)[1]
            products = db.get_document("loja_products") or {}
            product = products.get(product_id)
            if not product:
                return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
            current = str((product.get("info") or {}).get("delivery_type") or "automatic")
            select = disnake.ui.StringSelect(
                custom_id=f"Loja_ProdutoDeliverySelect:{product_id}",
                placeholder="Selecione o estilo de entrega",
                options=[
                    disnake.SelectOption(
                        label="Entrega Automática",
                        value="automatic",
                        description="O bot libera o estoque após a aprovação.",
                        emoji=getattr(emoji, "truck", emoji.cardbox),
                        default=current == "automatic",
                    ),
                    disnake.SelectOption(
                        label="Entrega Manual",
                        value="manual",
                        description="A equipe conclui a entrega manualmente.",
                        emoji=getattr(emoji, "member", emoji.config),
                        default=current == "manual",
                    ),
                ],
            )
            return await inter.response.send_message(
                f"{getattr(emoji, 'truck', emoji.cardbox)} **Estilo de Entrega**\nEscolha como este produto será entregue.",
                components=[disnake.ui.ActionRow(select)],
                ephemeral=True,
            )

        if custom_id.startswith("Loja_ConfigurarProduto"):
            _, product_id = inter.component.custom_id.split(":", 1)
            mode = db.get_document("custom_mode").get("mode")
            panel_data = ConfigurarProduto.panel(inter, product_id)
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                await inter.edit_original_message(content=None, **panel_data)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(**panel_data)
        elif inter.component.custom_id.startswith("Loja_ProdutosRelacionados:"):
            _, product_id = inter.component.custom_id.split(":", 1)
            products = db.get_document("loja_products") or {}
            product = products.get(product_id)
            if not product:
                return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
            current = {str(value) for value in product.get("related_products", [])}
            options = [
                disnake.SelectOption(
                    label=str(data.get("name", "Produto"))[:100],
                    value=str(other_id),
                    description="Recomendado após a compra"[:100],
                    emoji=emoji.cardbox,
                    default=str(other_id) in current,
                )
                for other_id, data in products.items()
                if str(other_id) != str(product_id)
            ][:25]
            if not options:
                return await inter.response.send_message(
                    f"{emoji.interrogation} Crie outro produto antes de configurar recomendações.",
                    ephemeral=True,
                )
            select = disnake.ui.StringSelect(
                custom_id=f"Loja_RelatedSelect:{product_id}",
                placeholder="Selecione até 3 produtos",
                min_values=0,
                max_values=min(3, len(options)),
                options=options,
            )
            await inter.response.send_message(
                f"{emoji.cardbox} **Produtos relacionados**\nSelecione até três opções para recomendar depois da compra.",
                components=[disnake.ui.ActionRow(select)],
                ephemeral=True,
            )

        elif inter.component.custom_id.startswith("Loja_AtualizarProduto:"):
            _, product_id = inter.component.custom_id.split(":", 1)
            await inter.response.defer(ephemeral=True)

            products = db.get_document("loja_products")
            product = products.get(product_id)
            if not product:
                await inter.followup.send(
                    content=f"{emoji.wrong} Produto não encontrado.",
                    ephemeral=True
                )
                return

            total = 0
            updated = 0
            removed = 0
            skipped = 0

            original_messages = product.get("messages") or []
            new_messages = []

            for m in original_messages:
                try:
                    total += 1
                    guild_id = m.get("guild_id")
                    channel_id = m.get("channel_id")
                    message_id = m.get("message_id")
                    mode_saved = m.get("mode")
                    formatted_desc = m.get("formatted_desc", True)  # Padrão: formatada

                    if not (guild_id and channel_id and message_id):
                        # entrada inválida: remover
                        removed += 1
                        continue
                    if guild_id != inter.guild.id:
                        # não pertence a esta guild: manter
                        new_messages.append(m)
                        skipped += 1
                        continue
                    channel = inter.guild.get_channel(int(channel_id))
                    if channel is None:
                        # canal não existe mais
                        removed += 1
                        continue
                    try:
                        msg = await channel.fetch_message(int(message_id))
                    except disnake.NotFound:
                        # mensagem não existe mais
                        removed += 1
                        continue

                    # Usar métodos de SendProduct que respeitam preferências e botões customizados
                    from .send import SendProduct
                    send_cog = None
                    for cog in inter.client.cogs.values():
                        if isinstance(cog, SendProduct):
                            send_cog = cog
                            break
                    
                    if not send_cog:
                        send_cog = SendProduct(inter.bot)
                    
                    if mode_saved == "text":
                        await msg.edit(
                            content=send_cog._build_text_content(product),
                            embed=None,
                            components=send_cog._create_buy_button(product_id),
                        )
                        updated += 1
                        new_messages.append(m)
                    elif mode_saved == "legacy_basic":
                        await msg.edit(
                            content=None,
                            embed=send_cog._build_basic_legacy_embed(product),
                            components=send_cog._create_buy_button(product_id),
                        )
                        updated += 1
                        new_messages.append(m)
                    elif mode_saved == "legacy":
                        embed = send_cog._build_legacy_embed(product, inter.guild, formatted_desc=formatted_desc)
                        components = send_cog._create_buy_button(product_id)
                        await msg.edit(content=None, embed=embed, components=components)
                        updated += 1
                        new_messages.append(m)
                    elif mode_saved in ("container_outside", "container_inside"):
                        image_inside = (mode_saved == "container_inside")
                        comps = send_cog._build_container(product, image_inside=image_inside, product_id=product_id, formatted_desc=formatted_desc)
                        await msg.edit(components=comps, flags=disnake.MessageFlags(is_components_v2=True))
                        updated += 1
                        new_messages.append(m)
                    else:
                        skipped += 1
                        new_messages.append(m)
                except Exception:
                    skipped += 1
                    new_messages.append(m)

            # Se houve remoções, salvar alterações na database
            if len(new_messages) != len(original_messages):
                products[product_id]["messages"] = new_messages
                db.save_document("loja_products", products)

            color_data = db.get_document("custom_colors") or {}
            primary_color_hex = color_data.get("primary")
            container_kwargs = {}
            if primary_color_hex:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

            result = disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Sincronização de Produto"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"**Produto:** `{product.get('name')}`\n"
                    f"**Total de mensagens:** `{total}`\n"
                    f"**Atualizadas:** `{updated}`\n"
                    f"**Removidas:** `{removed}`\n"
                    f"**Ignoradas:** `{skipped}`"
                ),
                **container_kwargs
            )
            await inter.followup.send(components=[result], ephemeral=True, flags=disnake.MessageFlags(is_components_v2=True))

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = str(inter.component.custom_id or "")
        if custom_id.startswith("Loja_ProdutoDeliverySelect:"):
            product_id = custom_id.split(":", 1)[1]
            value = str(inter.values[0]) if inter.values else "automatic"
            if value not in {"automatic", "manual"}:
                return await inter.response.send_message(f"{emoji.wrong} Estilo inválido.", ephemeral=True)
            products = db.get_document("loja_products") or {}
            product = products.get(product_id)
            if not product:
                return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
            product.setdefault("info", {})["delivery_type"] = value
            product["info"]["updated_at"] = int(disnake.utils.utcnow().timestamp())
            products[product_id] = product
            db.save_document("loja_products", products)
            return await inter.response.send_message(
                f"{emoji.correct} Estilo de entrega atualizado para **{'Automático' if value == 'automatic' else 'Manual'}**.",
                ephemeral=True,
            )

        if custom_id.startswith("Loja_RelatedSelect:"):
            product_id = inter.component.custom_id.split(":", 1)[1]
            products = db.get_document("loja_products") or {}
            if product_id not in products:
                return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
            products[product_id]["related_products"] = list(inter.values)[:3]
            products[product_id].setdefault("info", {})["updated_at"] = int(disnake.utils.utcnow().timestamp())
            db.save_document("loja_products", products)
            return await inter.response.send_message(
                f"{emoji.correct} Recomendações atualizadas: `{len(inter.values[:3])}` produto(s).",
                ephemeral=True,
            )

        if inter.component.custom_id == "Loja_Produtos_Select":
            product_id = inter.values[0]
            mode = db.get_document("custom_mode").get("mode")
            
            # Verificar se a interação já foi respondida antes de fazer defer
            if not inter.response.is_done():
                try:
                    await inter.response.defer()
                except:
                    pass  # Another listener already responded
            
            panel_data = ConfigurarProduto.panel(inter, product_id)
            
            if mode == "embed":
                await inter.edit_original_message(content=None, **panel_data)
            else:
                await inter.edit_original_message(**panel_data)

def setup(bot: commands.Bot):
    bot.add_cog(ConfigurarProduto(bot))