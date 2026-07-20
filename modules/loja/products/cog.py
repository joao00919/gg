from disnake.ext import commands, tasks
import disnake

from functions.emoji import emoji
from functions.message import message, embed_message
from functions.database import database as db
from functions.utils import utils
from modules.loja.cart.stock_manager import StockManager
from functions.interaction_runtime import respond_panel
from ..status import sales_enabled
from ..product_panels import get_panels, create_panel, build_admin_payload

def _product_description(product: dict) -> str:
    info = product.get("info") or {}
    fields = product.get("campos") or {}
    text = str(info.get("description") or product.get("description") or "").strip()
    if not text:
        for field in fields.values():
            if not isinstance(field, dict):
                continue
            text = str(field.get("description") or field.get("pre_description") or field.get("instructions") or "").strip()
            if text:
                break
    if not text:
        text = f"{product.get('name') or 'Produto'} disponível para compra."
    return " ".join(text.split())[:100]


def _product_emoji(product: dict):
    info = product.get("info") or {}
    raw = info.get("emoji") or product.get("emoji")
    if not raw:
        for field in (product.get("campos") or {}).values():
            if isinstance(field, dict) and field.get("emoji"):
                raw = field.get("emoji")
                break
    if raw:
        try:
            return disnake.PartialEmoji.from_str(str(raw))
        except Exception:
            pass
    return emoji.cardbox


class CreateStorePanelModal(disnake.ui.Modal):
    def __init__(self):
        super().__init__(
            title="Criar novo painel",
            custom_id="Loja_CriarPainel_Modal",
            components=[
                disnake.ui.TextInput(
                    label="Nome do painel",
                    placeholder="Ex.: Produtos Premium",
                    custom_id="panel_name",
                    min_length=1,
                    max_length=100,
                    required=True,
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        name = str(inter.text_values.get("panel_name") or "").strip()
        if not name:
            return await inter.response.send_message(f"{emoji.wrong} Informe um nome válido.", ephemeral=True)
        panel_id, _ = create_panel(name, getattr(inter.user, "id", 0))
        payload = dict(build_admin_payload(panel_id))
        payload.pop("flags", None)
        await respond_panel(inter, payload, prefer_edit=True)


class GerenciarProdutos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def gerar_dropdown_produtos(self, products: dict, page: int = 0, duplicar_mode: bool = False) -> list:
        """Gera dropdowns paginados para produtos (25 por página)
        
        Args:
            products: Dicionário de produtos
            page: Número da página (não usado mais, mantido para compatibilidade)
            duplicar_mode: Se True, usa custom_id para duplicação
        """
        if not products:
            custom_id = "Loja_DuplicarProduto_Select" if duplicar_mode else "Loja_Produtos_Select"
            return [disnake.ui.StringSelect(
                placeholder="Nenhum produto encontrado",
                options=[disnake.SelectOption(label="Nenhum produto encontrado", value="disabled")],
                custom_id=custom_id,
                disabled=True
            )]
        
        # Converter para lista e ordenar por nome
        product_list = sorted(products.items(), key=lambda x: x[1].get("name", "").lower())
        total_products = len(product_list)
        
        # Calcular paginação
        items_per_page = 25
        total_pages = (total_products + items_per_page - 1) // items_per_page
        
        # Se só tem uma página, retornar dropdown único
        if total_pages == 1:
            options = []
            for product_id, product in product_list:
                product_name = product.get("name", "Sem nome")
                if len(product_name) > 80:
                    product_name = product_name[:77] + "..."
                
                campos_count = len(product.get("campos", {}))
                cupons_count = len(product.get("cupons", {}))
                description = _product_description(product)
                
                if len(description) > 100:
                    description = description[:97] + "..."
                
                options.append(disnake.SelectOption(
                    label=product_name,
                    value=product_id,
                    description=description,
                    emoji=_product_emoji(product),
                ))
            
            custom_id = "Loja_DuplicarProduto_Select" if duplicar_mode else "Loja_Produtos_Select"
            return [disnake.ui.StringSelect(
                placeholder=f"[{total_products}] Selecione um produto",
                options=options,
                custom_id=custom_id
            )]
        
        # Múltiplas páginas - criar dropdowns
        dropdowns = []
        for page_num in range(total_pages):
            start_idx = page_num * items_per_page
            end_idx = min(start_idx + items_per_page, total_products)
            page_products = product_list[start_idx:end_idx]
            
            options = []
            for product_id, product in page_products:
                product_name = product.get("name", "Sem nome")
                if len(product_name) > 80:
                    product_name = product_name[:77] + "..."
                
                campos_count = len(product.get("campos", {}))
                cupons_count = len(product.get("cupons", {}))
                description = _product_description(product)
                
                if len(description) > 100:
                    description = description[:97] + "..."
                
                options.append(disnake.SelectOption(
                    label=product_name,
                    value=product_id,
                    description=description,
                    emoji=_product_emoji(product),
                ))
            
            # Placeholder indicando página e intervalo
            placeholder = f"[Página {page_num + 1}/{total_pages}] Produtos {start_idx + 1}-{end_idx}"
            
            custom_id_prefix = "Loja_DuplicarProduto_Select" if duplicar_mode else "Loja_Produtos_Select"
            dropdowns.append(disnake.ui.StringSelect(
                placeholder=placeholder,
                options=options,
                custom_id=f"{custom_id_prefix}_Page{page_num}"
            ))
        
        return dropdowns

    @staticmethod
    def _page_bounds(total: int, page: int, per_page: int = 25) -> tuple[int, int, int, int]:
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(0, min(int(page), total_pages - 1))
        start = page * per_page
        end = min(start + per_page, total)
        return page, total_pages, start, end

    @staticmethod
    def _product_select(products: dict, page: int, panel_page: int) -> disnake.ui.StringSelect:
        items = sorted(products.items(), key=lambda item: str((item[1] or {}).get("name", "")).lower())
        page, total_pages, start, end = GerenciarProdutos._page_bounds(len(items), page)
        options = []
        for product_id, product in items[start:end]:
            product = product or {}
            options.append(disnake.SelectOption(
                label=str(product.get("name") or product_id)[:100],
                value=str(product_id),
                description=_product_description(product),
                emoji=_product_emoji(product),
            ))
        if not options:
            options = [disnake.SelectOption(label="Nenhum produto cadastrado", value="disabled")]
        interval = f"{start + 1} a {end}" if end > start else "0 a 0"
        return disnake.ui.StringSelect(
            custom_id=f"Loja_Produtos_Select:{page}:{panel_page}",
            placeholder=f"[{page + 1}] Selecione um produto ({interval})" if end > start else "Nenhum produto cadastrado",
            options=options,
            disabled=end <= start,
        )

    @staticmethod
    def _panel_select(panels: dict, product_page: int, page: int) -> disnake.ui.StringSelect:
        items = sorted(panels.items(), key=lambda item: str((item[1] or {}).get("name", "")).lower())
        page, total_pages, start, end = GerenciarProdutos._page_bounds(len(items), page)
        options = []
        for panel_id, panel in items[start:end]:
            panel = panel or {}
            options.append(disnake.SelectOption(
                label=str(panel.get("name") or panel_id)[:100],
                value=str(panel_id),
                description=(
                    f"Produtos: {len(panel.get('product_ids') or [])} | "
                    f"Status: {'Ativo' if panel.get('active', True) else 'Inativo'}"
                )[:100],
                emoji=emoji.commands,
            ))
        if not options:
            options = [disnake.SelectOption(label="Nenhum painel cadastrado", value="disabled")]
        interval = f"{start + 1} a {end}" if end > start else "0 a 0"
        return disnake.ui.StringSelect(
            custom_id=f"Loja_Paineis_Select:{product_page}:{page}",
            placeholder=f"[{page + 1}] Selecione um painel ({interval})" if end > start else "Nenhum painel cadastrado",
            options=options,
            disabled=end <= start,
        )

    def panel(self, inter: disnake.MessageInteraction, product_page: int = 0, panel_page: int = 0):
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            return self._panel_embed(inter, product_page=product_page, panel_page=panel_page)
        return self._panel_components(inter, product_page=product_page, panel_page=panel_page)

    def _panel_components(self, inter: disnake.MessageInteraction, product_page: int = 0, panel_page: int = 0) -> dict:
        products = db.get_document("loja_products") or {}
        panels = get_panels()
        product_page, product_pages, _, _ = self._page_bounds(len(products), product_page)
        panel_page, panel_pages, _, _ = self._page_bounds(len(panels), panel_page)
        sales_text = "Ligado" if sales_enabled() else "Desligado"

        return {"components": [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.zenyx2}\n-# Painel > Loja > **Produtos**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(f"Produtos Totais: `{len(products)}` | Vendas: `{sales_text}`"),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Criar Produto", style=disnake.ButtonStyle.success, emoji=emoji.plus, custom_id="Loja_CriarProduto"),
                    disnake.ui.Button(label="←", style=disnake.ButtonStyle.secondary, custom_id=f"Loja_Produtos_Nav:product_prev:{product_page}:{panel_page}", disabled=product_page <= 0),
                    disnake.ui.Button(label=f"{product_page + 1}/{product_pages}", style=disnake.ButtonStyle.secondary, custom_id="Loja_Produtos_PageInfo", disabled=True),
                    disnake.ui.Button(label="→", style=disnake.ButtonStyle.secondary, custom_id=f"Loja_Produtos_Nav:product_next:{product_page}:{panel_page}", disabled=product_page >= product_pages - 1),
                ),
                disnake.ui.ActionRow(self._product_select(products, product_page, panel_page)),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(f"Painéis Totais: `{len(panels)}` | Vendas: `{sales_text}`"),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Criar Painel", style=disnake.ButtonStyle.success, emoji=emoji.plus, custom_id="Loja_CriarPainel"),
                    disnake.ui.Button(label="←", style=disnake.ButtonStyle.secondary, custom_id=f"Loja_Produtos_Nav:panel_prev:{product_page}:{panel_page}", disabled=panel_page <= 0),
                    disnake.ui.Button(label=f"{panel_page + 1}/{panel_pages}", style=disnake.ButtonStyle.secondary, custom_id="Loja_Paineis_PageInfo", disabled=True),
                    disnake.ui.Button(label="→", style=disnake.ButtonStyle.secondary, custom_id=f"Loja_Produtos_Nav:panel_next:{product_page}:{panel_page}", disabled=panel_page >= panel_pages - 1),
                ),
                disnake.ui.ActionRow(self._panel_select(panels, product_page, panel_page)),
                **({"accent_colour": disnake.Colour(int((db.get_document("custom_colors") or {}).get("primary", "#5865F2").replace("#", ""), 16))} if (db.get_document("custom_colors") or {}).get("primary") else {})
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.secondary, emoji=emoji.back, custom_id="Painel_Loja")),
        ]}

    def _panel_embed(self, inter: disnake.MessageInteraction, product_page: int = 0, panel_page: int = 0) -> dict:
        products = db.get_document("loja_products") or {}
        panels = get_panels()
        product_page, product_pages, _, _ = self._page_bounds(len(products), product_page)
        panel_page, panel_pages, _, _ = self._page_bounds(len(panels), panel_page)
        sales_text = "Ligado" if sales_enabled() else "Desligado"
        embed = disnake.Embed(
            title=f"{emoji.zenyx2} Produtos",
            description=(
                f"-# Painel > Loja > **Produtos**\n\n"
                f"Produtos Totais: `{len(products)}` | Vendas: `{sales_text}`\n"
                f"Painéis Totais: `{len(panels)}` | Vendas: `{sales_text}`"
            ),
        )
        return {"embed": embed, "components": [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Criar Produto", style=disnake.ButtonStyle.success, emoji=emoji.plus, custom_id="Loja_CriarProduto"),
                disnake.ui.Button(label="←", custom_id=f"Loja_Produtos_Nav:product_prev:{product_page}:{panel_page}", disabled=product_page <= 0),
                disnake.ui.Button(label=f"{product_page + 1}/{product_pages}", custom_id="Loja_Produtos_PageInfo", disabled=True),
                disnake.ui.Button(label="→", custom_id=f"Loja_Produtos_Nav:product_next:{product_page}:{panel_page}", disabled=product_page >= product_pages - 1),
            ),
            disnake.ui.ActionRow(self._product_select(products, product_page, panel_page)),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Criar Painel", style=disnake.ButtonStyle.success, emoji=emoji.plus, custom_id="Loja_CriarPainel"),
                disnake.ui.Button(label="←", custom_id=f"Loja_Produtos_Nav:panel_prev:{product_page}:{panel_page}", disabled=panel_page <= 0),
                disnake.ui.Button(label=f"{panel_page + 1}/{panel_pages}", custom_id="Loja_Paineis_PageInfo", disabled=True),
                disnake.ui.Button(label="→", custom_id=f"Loja_Produtos_Nav:panel_next:{product_page}:{panel_page}", disabled=panel_page >= panel_pages - 1),
            ),
            disnake.ui.ActionRow(self._panel_select(panels, product_page, panel_page)),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id="Painel_Loja")),
        ]}

    def _panel_duplicar_produto(self, inter: disnake.MessageInteraction) -> dict:
        """Painel para selecionar produto a duplicar"""
        products = db.get_document("loja_products") or {}
        dropdowns = self.gerar_dropdown_produtos(products, duplicar_mode=True)

        color_data = db.get_document("custom_colors")
        primary_color_hex = color_data.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

        # Criar ActionRows para os dropdowns
        dropdown_rows = [disnake.ui.ActionRow(dropdown) for dropdown in dropdowns]
        
        # Adicionar dropdowns e botão ao container
        container_items = [
            disnake.ui.TextDisplay(f"# {emoji.zenyx2}\n-# Painel > Loja > **Gerenciar Produtos** > **Duplicar Produto**"),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay(f"Selecione um produto abaixo para duplicá-lo."),
            disnake.ui.Separator(),
        ]
        
        # Adicionar todos os dropdowns
        container_items.extend(dropdown_rows)

        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            embed_kwargs = {}
            if primary_color_hex:
                embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)
            
            embed = disnake.Embed(
                description=f"-# Painel > Loja > **Gerenciar Produtos** > **Duplicar Produto**\n\nSelecione um produto abaixo para duplicá-lo.",
                **embed_kwargs
            )
            
            components = []
            for dropdown in dropdowns:
                components.append(disnake.ui.ActionRow(dropdown))
            
            components.append(disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Loja_Produtos")))
            
            return {"embed": embed, "components": components}

        return {"components": [
            disnake.ui.Container(*container_items, **container_kwargs),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Loja_Produtos")),
        ]}

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")

        if cid.startswith("Loja_Produtos_Nav:"):
            try:
                _, action, product_page, panel_page = cid.split(":", 3)
                product_page = int(product_page)
                panel_page = int(panel_page)
            except (TypeError, ValueError):
                return await inter.response.send_message(f"{emoji.wrong} Página inválida.", ephemeral=True)
            if action == "product_prev":
                product_page -= 1
            elif action == "product_next":
                product_page += 1
            elif action == "panel_prev":
                panel_page -= 1
            elif action == "panel_next":
                panel_page += 1
            return await respond_panel(
                inter, self.panel(inter, product_page=product_page, panel_page=panel_page), prefer_edit=True
            )

        if cid == "Loja_CriarPainel":
            return await inter.response.send_modal(CreateStorePanelModal())

        if cid == "Loja_Produtos":
            return await respond_panel(inter, self.panel(inter), prefer_edit=True)
        
        elif cid == "Loja_DuplicarProduto":
            mode = db.get_document("custom_mode").get("mode")
            msg_handler = embed_message if mode == "embed" else message
            await msg_handler.wait(inter, send=False)

            panel_data = self._panel_duplicar_produto(inter)
            if "embed" in panel_data:
                await inter.edit_original_message(content=None, **panel_data)
            else:
                await inter.edit_original_message(**panel_data, flags=disnake.MessageFlags(is_components_v2=True))
        
        # Validar mensagens salvas na database
        elif inter.component.custom_id == "Loja_Produtos_ValidarMensagens":
            await inter.response.defer(ephemeral=True)
            products = db.get_document("loja_products") or {}
            total_checked = 0
            total_removed = 0
            changed = False
            for product_id, p in products.items():
                msgs = p.get("messages") or []
                if not isinstance(msgs, list) or not msgs:
                    continue
                new_msgs = []
                for m in msgs:
                    try:
                        msg_guild_id = m.get("guild_id")
                        msg_channel_id = m.get("channel_id")
                        msg_id = m.get("message_id")
                        if not (msg_channel_id and msg_id):
                            # inválido
                            total_removed += 1
                            continue
                        # validar apenas mensagens deste servidor para evitar falsas remoções
                        if msg_guild_id and msg_guild_id != inter.guild.id:
                            new_msgs.append(m)
                            continue
                        channel = inter.guild.get_channel(int(msg_channel_id))
                        if channel is None:
                            total_removed += 1
                            continue
                        # tentar buscar a mensagem
                        try:
                            await channel.fetch_message(int(msg_id))
                            new_msgs.append(m)  # existe
                        except disnake.NotFound:
                            total_removed += 1
                        except (disnake.Forbidden, disnake.HTTPException):
                            # sem permissão ou erro transitório: manter por segurança
                            new_msgs.append(m)
                    finally:
                        total_checked += 1
                if len(new_msgs) != len(msgs):
                    products[product_id]["messages"] = new_msgs
                    changed = True
            if changed:
                db.save_document("loja_products", products)

            # construir retorno visual
            color_data = db.get_document("custom_colors") or {}
            primary_color_hex = color_data.get("primary")
            container_kwargs = {}
            if primary_color_hex:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

            result_container = disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.zenyx2}\n-# Loja > **Validar Mensagens**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"**Mensagens verificadas:** `{total_checked}`\n"
                    f"**Removidas da database:** `{total_removed}`\n"
                    f"**Documento:** `loja_products`"
                ),
                **container_kwargs
            )
            await inter.followup.send(components=[result_container], ephemeral=True, flags=disnake.MessageFlags(is_components_v2=True))

    @tasks.loop(hours=1)
    async def _auto_validate_messages(self):
        products = db.get_document("loja_products") or {}
        changed = False
        for product_id, p in products.items():
            msgs = p.get("messages") or []
            if not isinstance(msgs, list) or not msgs:
                continue
            new_msgs = []
            for m in msgs:
                try:
                    gid = m.get("guild_id")
                    cid = m.get("channel_id")
                    mid = m.get("message_id")
                    if not (cid and mid and gid):
                        continue
                    guild = self.bot.get_guild(int(gid)) if gid else None
                    if guild is None:
                        continue
                    channel = guild.get_channel(int(cid)) if cid else None
                    if channel is None:
                        continue
                    try:
                        await channel.fetch_message(int(mid))
                        new_msgs.append(m)
                    except disnake.NotFound:
                        pass
                    except (disnake.Forbidden, disnake.HTTPException):
                        new_msgs.append(m)
                except Exception:
                    pass
            if len(new_msgs) != len(msgs):
                products[product_id]["messages"] = new_msgs
                changed = True
        if changed:
            db.save_document("loja_products", products)

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")

        if cid.startswith("Loja_Produtos_Select"):
            product_id = str(inter.values[0]) if inter.values else ""
            if product_id == "disabled" or not product_id:
                return await inter.response.defer()
            from .product.configurar import ConfigurarProduto
            return await respond_panel(
                inter, ConfigurarProduto.panel(inter, product_id), prefer_edit=True
            )

        if cid.startswith("Loja_Paineis_Select"):
            panel_id = str(inter.values[0]) if inter.values else ""
            if panel_id == "disabled" or not panel_id:
                return await inter.response.defer()
            if panel_id not in get_panels():
                return await inter.response.send_message(f"{emoji.wrong} Painel não encontrado.", ephemeral=True)
            payload = dict(build_admin_payload(panel_id))
            payload.pop("flags", None)
            return await respond_panel(inter, payload, prefer_edit=True)

        if cid.startswith("Loja_DuplicarProduto_Select"):
            product_id = str(inter.values[0]) if inter.values else ""
            if product_id == "disabled" or not product_id:
                return await inter.response.defer()
            from .duplicate import DuplicateProductModal
            return await inter.response.send_modal(DuplicateProductModal(product_id))

    @_auto_validate_messages.before_loop
    async def _before_auto_validate_messages(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._auto_validate_messages.is_running():
            self._auto_validate_messages.start()

    def cog_unload(self):
        if self._auto_validate_messages.is_running():
            self._auto_validate_messages.cancel()

def setup(bot: commands.Bot):
    bot.add_cog(GerenciarProdutos(bot))