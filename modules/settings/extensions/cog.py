import disnake
from disnake.ext import commands, tasks
import aiohttp
import asyncio
import json
import io
import os

from functions.emoji import emoji
from functions.database import database as db
from functions.message import message, embed_message
from . import subscription_manager as subs


class ExtensionsPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = os.getenv("ZYNEXGEN_API_URL", "").strip().rstrip("/")
        self.bot_secret = os.getenv("ZYNEXGEN_BOT_SECRET", "").strip()
        self.restock_tasks = {}  # Store active restock tasks
        self.payment_cooldowns = {}  # Store payment cooldowns

    def _get_extensions_config(self) -> dict:
        """Obtém configuração de extensões"""
        return db.obter("configs/config_extensions.json")

    def _get_syncgen_status(self) -> dict:
        """Obtém status da extensão Sync Gen"""
        return db.obter("database/syncgen.json")

    def _get_livestock_config(self) -> dict:
        """Obtém configuração de Live Stock"""
        data = db.obter("database/syncgen.json")
        return data.get("livestock", {})

    def panel_payload(self, inter: disnake.Interaction, *, back_custom_id: str = "Painel_Configuracoes") -> dict:
        """Retorna o painel sem responder à interação, permitindo reutilização na Loja."""
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        extensions_config = self._get_extensions_config()
        if mode == "embed":
            embed, components = self._build_embed_panel(inter, extensions_config, back_custom_id=back_custom_id)
            return {"embed": embed, "components": components}
        return {"components": self._build_components_panel(inter, extensions_config, back_custom_id=back_custom_id)}

    async def display_extensions_panel(self, inter: disnake.MessageInteraction):
        """Exibe o painel principal de extensões"""
        mode = db.get_document("custom_mode").get("mode")
        extensions_config = self._get_extensions_config()

        if mode == "embed":
            await embed_message.wait(inter, send=False)
            embed, components = self._build_embed_panel(inter, extensions_config)
            await inter.edit_original_message(content=None, embed=embed, components=components)
        else:
            await message.wait(inter, send=False)
            components = self._build_components_panel(inter, extensions_config)
            await inter.edit_original_message(components=components)

    def _build_components_panel(self, inter: disnake.MessageInteraction, extensions_config: dict, *, back_custom_id: str = "Painel_Configuracoes") -> list:
        """Constrói painel em modo components - Visual moderno"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        # Status das extensões
        boost_enabled = subs.is_extension_active("boost")
        syncgen_data = self._get_syncgen_status()
        syncgen_enabled = syncgen_data.get("enabled", True)
        syncgen_integrated = syncgen_data.get("integrated_user_id") is not None

        # Construir status do Sync Gen
        if syncgen_enabled and syncgen_integrated:
            syncgen_status = f"{emoji.on} Ativo"
            syncgen_user = syncgen_data.get("integrated_user", "N/A")
        elif syncgen_enabled:
            syncgen_status = f"{emoji.warn} Não integrado"
            syncgen_user = None
        else:
            syncgen_status = f"{emoji.off} Desativado"
            syncgen_user = None

        # Construir status do Boost
        boost_status = f"{emoji.on} Ativo" if boost_enabled else f"{emoji.off} Desativado"

        # Opções para o select menu de extensões
        extension_options = [
            disnake.SelectOption(
                label="Sync Gen",
                value="syncgen",
                emoji=emoji.link,
                description=f"{'Ativo' if syncgen_enabled else 'Não integrado'} - Gerador de contas"
            ),
            disnake.SelectOption(
                label="Sync Boost",
                value="boost",
                emoji=emoji.boost,
                description=f"{'Ativo' if boost_enabled else 'Desativado'} - Venda de boosts"
            )
        ]

        # Sync Gen info
        syncgen_info = f"{emoji.link} **Sync Gen (Grátis)** — {syncgen_status}"
        if syncgen_user:
            syncgen_info += f"\n-# {emoji.member} Integrado com: `{syncgen_user}`"
        else:
            syncgen_info += f"\n-# Gerador de contas com integração ao painel web"

        # Sync Boost info
        boost_info = f"{emoji.boost} **Sync Boost** — {boost_status}"
        boost_info += f"\n-# Sistema de venda de boosts para servidores"

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(
                    f"# {emoji.z0}\n"
                    f"-# Painel > Configurações > **Extensões**"
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(
                    f"Gerencie as extensões disponíveis do bot.\n"
                    f"Selecione uma extensão abaixo para acessar suas configurações."
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(syncgen_info),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(boost_info),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="Extensions_Select",
                        placeholder=f"[2] Extensões disponíveis",
                        options=extension_options
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id=back_custom_id
                ),
                disnake.ui.Button(
                    label="Comprar Extensões",
                    style=disnake.ButtonStyle.green,
                    emoji=emoji.cart,
                    custom_id="Extensions_Purchase"
                ),
                disnake.ui.Button(
                    label="",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.information,
                    custom_id="Extensions_Info"
                )
            )
        ]

    def _build_embed_panel(self, inter: disnake.MessageInteraction, extensions_config: dict, *, back_custom_id: str = "Painel_Configuracoes") -> tuple:
        """Constrói painel em modo embed"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        # Status das extensões
        boost_enabled = subs.is_extension_active("boost")
        boost_status = f"{emoji.on} Ativada" if boost_enabled else f"{emoji.off} Desativada"

        syncgen_data = self._get_syncgen_status()
        syncgen_enabled = syncgen_data.get("enabled", True)
        syncgen_integrated = syncgen_data.get("integrated_user_id") is not None

        if syncgen_enabled and syncgen_integrated:
            syncgen_status = f"{emoji.on} Ativo"
        elif syncgen_enabled:
            syncgen_status = f"{emoji.warn} Não integrado"
        else:
            syncgen_status = f"{emoji.off} Desativado"

        embed = disnake.Embed(
            title=f"{emoji.commands} Extensões",
            description=(
                "Gerencie as extensões disponíveis do bot.\n"
                "Clique em uma extensão para acessar suas configurações."
            ),
        )

        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            embed.color = primary_color

        # Sync Gen Field
        syncgen_value = f"**Status:** {syncgen_status}\n"
        if syncgen_integrated:
            syncgen_value += f"**Usuário:** `{syncgen_data.get('integrated_user', 'N/A')}`\n"
        syncgen_value += "Gerador de contas com integração ao painel web."

        embed.add_field(
            name=f"{emoji.link} Sync Gen (Grátis)",
            value=syncgen_value,
            inline=False
        )

        # Sync Boost Field
        embed.add_field(
            name=f"{emoji.boost} Sync Boost",
            value=(
                f"**Status:** {boost_status}\n"
                f"Sistema de venda de boosts para servidores Discord."
            ),
            inline=False
        )




        # Opções para o select menu de extensões
        extension_options = [
            disnake.SelectOption(
                label="Sync Gen",
                value="syncgen",
                emoji=emoji.link,
                description=f"{'Ativo' if syncgen_enabled else 'Não integrado'} - Gerador de contas"
            ),
            disnake.SelectOption(
                label="Sync Boost",
                value="boost",
                emoji=emoji.boost,
                description=f"{'Ativo' if boost_enabled else 'Desativado'} - Venda de boosts"
            )
        ]

        components = [
            disnake.ui.ActionRow(
                disnake.ui.StringSelect(
                    custom_id="Extensions_Select",
                    placeholder=f"[2] Extensões disponíveis",
                    options=extension_options
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id=back_custom_id
                ),
                disnake.ui.Button(
                    label="",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.information,
                    custom_id="Extensions_Info"
                )
            )
        ]

        return embed, components

    # ==================== ZYNEX GEN PANEL ====================

    def _build_syncgen_panel(self, inter: disnake.MessageInteraction) -> list:
        """Constrói o painel do Sync Gen"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        status_data = self._get_syncgen_status()
        integrated_user = status_data.get("integrated_user", "Nenhum")
        is_integrated = status_data.get("integrated_user_id") is not None
        project_key = status_data.get("project_key")
        is_enabled = status_data.get("enabled", True)

        # Status info
        status_text = f"# {emoji.z0}\n-# Painel > Extensões > **Sync Gen**"

        info_lines = [
            f"{emoji.on if is_enabled else emoji.off} **Status:** {'Ativo' if is_enabled else 'Desativado'}",
            f"{emoji.member} **Usuário Integrado:** `{integrated_user}`"
        ]
        if project_key:
            info_lines.append(f"{emoji.folder} **Projeto Selecionado:** `{project_key}`")
            info_lines.append(f"-# Se você regenerou a key do projeto, selecione-o novamente.")

        info_text = "\n".join(info_lines)

        options = [
            disnake.SelectOption(
                label="Gerar Código",
                value="generate_code",
                emoji=emoji.link,
                description="Gera um código para vincular ao painel"
            ),
            disnake.SelectOption(
                label="Definir Projeto",
                value="select_project",
                emoji=emoji.folder,
                description="Define um projeto padrão para requisições"
            ),
            disnake.SelectOption(
                label="Configurar Extensão",
                value="configure_extension",
                emoji=emoji.settings,
                description="Gerenciar configurações avançadas"
            ),
            disnake.SelectOption(
                label="Tutorial",
                value="tutorial",
                emoji=emoji.fire,
                description="Aprenda a usar a extensão"
            )
        ]

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(status_text),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(info_text),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="SyncGen_MainSelect",
                        placeholder="[4] Selecione uma das ações.",
                        options=options,
                        disabled=not is_enabled
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Configuracoes_Extensoes"
                ),
                disnake.ui.Button(
                    label="Desativar" if is_enabled else "Ativar",
                    style=disnake.ButtonStyle.red if is_enabled else disnake.ButtonStyle.green,
                    emoji=emoji.off if is_enabled else emoji.on,
                    custom_id="SyncGen_Toggle"
                )
            )
        ]

    def _build_syncgen_config_panel(self, inter: disnake.MessageInteraction) -> list:
        """Constrói o painel de configuração do Sync Gen"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        options = [
            disnake.SelectOption(
                label="Gerar Streaming/Gaming",
                value="gen_streaming_gaming",
                emoji=emoji.controller,
                description="Gerar contas de serviços"
            ),
            disnake.SelectOption(
                label="Ativar Live-Stock em Produtos",
                value="live_stock",
                emoji=emoji.cart,
                description="Reabastecer produtos automaticamente"
            ),
            disnake.SelectOption(
                label="Personalizar Embeds",
                value="custom_embeds",
                emoji=emoji.paint,
                description="Em desenvolvimento"
            ),
            disnake.SelectOption(
                label="Ativar comando /gen",
                value="activate_gen",
                emoji=emoji.commands,
                description="Em desenvolvimento"
            )
        ]

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(
                    f"# {emoji.z0}\n"
                    f"-# Sync Gen > **Configurações**"
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(
                    f"-# Selecione uma opção para configurar."
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="SyncGen_ConfigSelect",
                        placeholder="Selecione uma configuração",
                        options=options
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Extensions_SyncGen"
                )
            )
        ]

    # ==================== BUTTON HANDLERS ====================

    @commands.Cog.listener("on_button_click")
    async def on_extensions_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id

        if custom_id == "Configuracoes_Extensoes":
            await self.display_extensions_panel(inter)

        elif custom_id == "Extensions_Info":
            await inter.response.send_message(
                f"{emoji.information if hasattr(emoji, 'information') else 'ℹ️'} **Sobre as Extensões**\n\n"
                f"Todas as extensões são nomeadas pela **Sync**, porém são oferecidas através de "
                f"**parcerias externas** com desenvolvedores e empresas especializadas.\n\n"
                f"Cada extensão possui funcionalidades únicas e podem requerer configuração adicional "
                f"ou integração com serviços externos para funcionamento completo.",
                ephemeral=True  
            )

        elif custom_id == "Extensions_Purchase":
            await self._show_purchase_panel(inter)

        elif custom_id == "Extensions_MyPayments":
            await self._show_my_payments(inter)

        elif custom_id == "Extensions_BackFromPurchase":
            await self.display_extensions_panel(inter)

        elif custom_id == "Extensions_BuyBoost":
            await self._create_boost_payment(inter)

        elif custom_id.startswith("Extensions_VerifyPayment_"):
            payment_id = custom_id.replace("Extensions_VerifyPayment_", "")
            await self._verify_payment(inter, payment_id)

        elif custom_id == "Extensions_RenewBoost":
            await self._create_boost_payment(inter)

        elif custom_id == "Extensions_SyncGen":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                # For embed mode, we still use components V2
                components = self._build_syncgen_panel(inter)
                await inter.edit_original_message(content=None, embed=None, components=components)
            else:
                await message.wait(inter, send=False)
                components = self._build_syncgen_panel(inter)
                await inter.edit_original_message(components=components)

        elif custom_id == "Extensions_Boost":
            boost_cog = self.bot.get_cog("BoostExtension")
            if boost_cog:
                await boost_cog.display_boost_panel(inter)

        elif custom_id == "SyncGen_Toggle":
            current_data = db.obter("database/syncgen.json")
            is_enabled = current_data.get("enabled", True)
            current_data["enabled"] = not is_enabled
            db.salvar("database/syncgen.json", current_data)

            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter, send=False)
            else:
                await message.wait(inter, send=False)
            components = self._build_syncgen_panel(inter)
            await inter.edit_original_message(components=components)

        elif custom_id == "SyncGen_BackToConfig":
            await message.wait(inter, send=False)
            components = self._build_syncgen_config_panel(inter)
            await inter.edit_original_message(components=components)

        elif custom_id == "SyncGen_ConfirmLiveStock":
            # Save that user accepted the live stock warning
            current_data = db.obter("database/syncgen.json")
            if "livestock" not in current_data:
                current_data["livestock"] = {}
            current_data["livestock"]["accepted_warning"] = True
            db.salvar("database/syncgen.json", current_data)

            await self._show_products_for_livestock(inter)

        elif custom_id == "SyncGen_CancelLiveStock":
            await message.wait(inter, send=False)
            components = self._build_syncgen_config_panel(inter)
            await inter.edit_original_message(components=components)

        elif custom_id == "SyncGen_LiveStockAnalytics":
            await self._show_livestock_analytics(inter)

        elif custom_id == "SyncGen_LiveStockNotifications":
            await self._toggle_livestock_notifications(inter)
        
        elif custom_id == "SyncGen_LiveStockProducts":
            await self._show_products_for_livestock(inter)

        elif custom_id.startswith("check_code_"):
            code = custom_id.replace("check_code_", "")
            await self._check_integration_code(inter, code)

    async def _check_integration_code(self, inter: disnake.MessageInteraction, code: str):
        """Verifica se o código foi integrado"""
        await inter.response.defer(ephemeral=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/bot/check-code/{code}",
                    headers={"x-bot-secret": self.bot_secret}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("redeemed"):
                            username = data.get("username")
                            user_id = data.get("redeemedBy")

                            # Update database
                            current_data = db.obter("database/syncgen.json")
                            current_data["integrated_user"] = username
                            current_data["integrated_user_id"] = user_id
                            current_data["project_key"] = None
                            db.salvar("database/syncgen.json", current_data)

                            await inter.followup.send(
                                f"{emoji.correct} **Sucesso!** Bot vinculado ao usuário: **{username}**\n\n"
                                f"Agora você pode selecionar um projeto em **Definir Projeto**.",
                                ephemeral=True
                            )

                            # Refresh the panel
                            mode = db.get_document("custom_mode").get("mode")
                            if mode == "embed":
                                await embed_message.wait(inter, send=False)
                            components = self._build_syncgen_panel(inter)
                            await inter.message.edit(components=components)
                        else:
                            await inter.followup.send(
                                f"{emoji.warn} Este código ainda não foi resgatado no site.\n\n"
                                f"Acesse https://loopgen.vercel.app/ e insira o código no dashboard.",
                                ephemeral=True
                            )
                    else:
                        await inter.followup.send(f"Erro ao verificar código: {response.status}", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Erro de conexão: {str(e)}", ephemeral=True)

    async def _show_my_payments(self, inter: disnake.MessageInteraction):
        """Mostra histórico de pagamentos do usuário"""
        mode = db.get_document("custom_mode").get("mode")
        user_id = str(inter.author.id)
        data = subs.get_user_payments(user_id)
        
        # Cores
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
            
        pending = data["pending"]
        history = data["history"]
        
        container_items = []
        
        # Header
        container_items.append(disnake.ui.TextDisplay(f"# {emoji.z0}\nMeus Pagamentos"))
        container_items.append(disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small))
        
        if not pending and not history:
             container_items.append(disnake.ui.TextDisplay("`Nenhum registro de pagamento encontrado.`"))
        else:
            if pending:
                container_items.append(disnake.ui.TextDisplay(f"### {emoji.time} Pendentes"))
                text = ""
                for p in pending:
                    ext_name = p.get('extension_id', 'Extensão').capitalize()
                    date_str = p.get('created_at', '')[:19].replace('T', ' ')
                    text += f"• **{ext_name}**: R$ {p['value']:.2f}\nCriado em: {date_str}\n"
                container_items.append(disnake.ui.TextDisplay(text))
                container_items.append(disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small))
                
            if history:
                container_items.append(disnake.ui.TextDisplay(f"### {emoji.correct} Realizados (Últimos 5)"))
                text = ""
                for h in history[:5]:
                    ext_name = h.get('extension_id', 'Extensão').capitalize()
                    date_str = h.get('completed_at', '')[:19].replace('T', ' ')
                    text += f"• **{ext_name}**: R$ {h['value']:.2f}\nStatus: {h.get('status')} - Data: {date_str}\n"
                container_items.append(disnake.ui.TextDisplay(text))

        container = disnake.ui.Container(*container_items, **container_kwargs)
        
        components = [
            container,
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Extensions_Purchase"
                )
            )
        ]
        
        if mode == "embed":
             await inter.response.edit_message(embed=None, components=components)
        else:
             await inter.response.edit_message(content=None, components=components)

    async def _show_purchase_panel(self, inter: disnake.MessageInteraction):
        """Mostra as extensões ativas para compra"""
        mode = db.get_document("custom_mode").get("mode")
        
        # Verificar status do Boost
        is_active = subs.is_extension_active("boost")
        expiry_date = subs.get_expiry_date("boost")
        
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
            
        # Select Menu de Compra
        purchase_select = disnake.ui.StringSelect(
            placeholder="[2] Selecione uma extensão...",
            custom_id="Extensions_Purchase_Select",
            min_values=1,
            max_values=1,
            options=[
                disnake.SelectOption(
                    label="Sync Gen (Grátis)",
                    value="purchase_syncgen",
                    description="Gerador de contas com integração web",
                    emoji=emoji.link
                ),
                disnake.SelectOption(
                    label="Sync Boost",
                    value="purchase_boost",
                    description="R$ 50,00 / mês - Sistema de boosts",
                    emoji=emoji.boost
                )
            ]
        )

        # Texto do Sync Boost (com expiração se ativo)
        boost_title = f"{emoji.boost} **Sync Boost (R$50 per/month)**"
        if is_active and expiry_date:
            boost_title = f"{emoji.boost} **Sync Boost (Expira: {expiry_date})**"

        container = disnake.ui.Container(
            disnake.ui.TextDisplay(
                f"# {emoji.z0}\n"
                f"-# Configurações > Extensões > **Comprar**"
            ),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            disnake.ui.TextDisplay(
                f"Adquira ou renove assinaturas para as extensões do bot."
            ),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            
            # Sync Gen Text
            disnake.ui.TextDisplay(
                f"{emoji.link} **Sync Gen (Grátis)**\n"
                f"-# Gerador de contas com integração ao painel web"
            ),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            
            # Sync Boost Text
            disnake.ui.TextDisplay(
                f"{boost_title}\n"
                f"-# Sistema completo de vendas de boosts"
            ),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            
            # Select Menu (Inside Container - Wrapped in ActionRow)
            disnake.ui.ActionRow(purchase_select),
            
            **container_kwargs
        )
        
        components = [
            container,
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Extensions_BackFromPurchase"
                ),
                disnake.ui.Button(
                    label="Meus Pagamentos",
                    style=disnake.ButtonStyle.secondary,
                    emoji=emoji.wallet,
                    custom_id="Extensions_MyPayments"
                )
            )
        ]
        
        if mode == "embed":
             await inter.response.edit_message(embed=None, components=components)
        else:
             await inter.response.edit_message(content=None, components=components)

    async def _create_boost_payment(self, inter: disnake.MessageInteraction):
        """Cria pagamento para o Boost"""
        import time
        user_id = str(inter.author.id)
        current_time = time.time()
        
        if user_id in self.payment_cooldowns:
            expiration = self.payment_cooldowns[user_id]
            if current_time < expiration:
                 await inter.response.send_message(
                     f"{emoji.time} Aguarde {int(expiration - current_time)}s para gerar outro pagamento.",
                     ephemeral=True
                 )
                 return

        self.payment_cooldowns[user_id] = current_time + 30

        await inter.response.defer(ephemeral=True)
        
        # Criar pagamento
        result = await subs.create_payment("boost", user_id)
        
        if not result["success"]:
            await inter.followup.send(
                f"{emoji.wrong} Erro ao criar pagamento: {result.get('error')}",
                ephemeral=True
            )
            return
            
        # Converter base64 para arquivo
        import base64
        import io
        
        qr_code_base64 = result["qrcode_url"]
        qr_code_data = qr_code_base64.split(",")[1]
        qr_code_bytes = base64.b64decode(qr_code_data)
        file = disnake.File(io.BytesIO(qr_code_bytes), filename="qrcode.png")
        
        payment_id = result["payment_id"]
        copy_paste = result["copy_paste"]
        
        # Embed de pagamento
        embed = disnake.Embed(
            title=f"{emoji.dollar} Pagamento Gerado",
            description=(
                f"Realize o pagamento via PIX para ativar o **Sync Boost**.\n\n"
                f"**Valor:** R$ {result['value']:.2f}\n"
                f"**Expiração:** 30 minutos"
            ),
            color=disnake.Color.green()
        )
        embed.set_image(url="attachment://qrcode.png")
        embed.add_field(name="Copia e Cola", value=f"```{copy_paste}```", inline=False)
        
        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Já efetuei o pagamento!",
                    style=disnake.ButtonStyle.success,
                    emoji=emoji.correct,
                    custom_id=f"Extensions_VerifyPayment_{payment_id}"
                )
            )
        ]
        
        await inter.followup.send(embed=embed, file=file, components=components, ephemeral=True)

    async def _verify_payment(self, inter: disnake.MessageInteraction, payment_id: str):
        """Verifica se o pagamento foi realizado"""
        await inter.response.defer(ephemeral=True)
        
        result = await subs.check_payment(payment_id)
        
        if not result["success"]:
            await inter.followup.send(
                f"{emoji.wrong} Erro ao verificar pagamento: {result.get('error')}",
                ephemeral=True
            )
            return
            
        status = result.get("status")
        
        if status == "COMPLETED":
            await inter.followup.send(
                f"{emoji.correct} **Pagamento Confirmado!**\n\n"
                f"A extensão **Sync Boost** foi ativada com sucesso.\n"
                f"Expira em: **{result.get('expires_at')}**",
                ephemeral=True
            )
            
            # Atualizar painel de compra
            await self._show_purchase_panel(inter)
            
        elif status == "PENDING" or status == "ACTIVE":
            await inter.followup.send(
                f"{emoji.time} **Pagamento Pendente**\n"
                f"Aguardando confirmação bancária...",
                ephemeral=True
            )
        else:
            await inter.followup.send(
                f"{emoji.wrong} Pagamento falhou ou expirou (Status: {status})",
                ephemeral=True
            )

    # ==================== DROPDOWN HANDLERS ====================

    @commands.Cog.listener("on_dropdown")
    async def on_syncgen_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id

        # Handler para o select menu de compra
        if custom_id == "Extensions_Purchase_Select":
            choice = inter.values[0]
            
            if choice == "purchase_syncgen":
                 await inter.response.send_message(
                     f"{emoji.link} **Sync Gen** é uma extensão gratuita e já está disponível para uso.",
                     ephemeral=True
                 )
            elif choice == "purchase_boost":
                 await self._create_boost_payment(inter)
            return

        # Handler para o select menu de extensões principais
        if custom_id == "Extensions_Select":
            choice = inter.values[0]

            if choice == "syncgen":
                mode = db.get_document("custom_mode").get("mode")
                if mode == "embed":
                    await embed_message.wait(inter, send=False)
                else:
                    await message.wait(inter, send=False)
                components = self._build_syncgen_panel(inter)
                await inter.edit_original_message(content=None, embed=None, components=components)

            elif choice == "boost":
                boost_cog = self.bot.get_cog("BoostExtension")
                if boost_cog:
                    await boost_cog.display_boost_panel(inter)
                else:
                    await inter.response.send_message(
                        f"{emoji.warn} Extensão Sync Boost não está disponível.",
                        ephemeral=True
                    )

            elif choice in ["members", "robux", "mods", "tools"]:
                await inter.response.send_message(
                    f"{emoji.warn} Esta extensão está **desativada** e será liberada em breve!",
                    ephemeral=True
                )
            return

        if custom_id == "SyncGen_MainSelect":
            choice = inter.values[0]

            if choice == "generate_code":
                await self._generate_code(inter)


            elif choice == "select_project":
                await self._show_project_selection(inter)

            elif choice == "configure_extension":
                status_data = self._get_syncgen_status()
                if not status_data.get("integrated_user_id"):
                    await inter.response.send_message(
                        f"{emoji.wrong} Você precisa vincular o bot a um usuário primeiro.\n\n"
                        f"Use a opção **Gerar Código** e siga o tutorial.",
                        ephemeral=True
                    )
                    return

                await message.wait(inter, send=False)
                components = self._build_syncgen_config_panel(inter)
                await inter.edit_original_message(components=components)

            elif choice == "tutorial":
                tutorial_text = (
                    f"# {emoji.fire} Tutorial de Integração\n\n"
                    f"**Passo 1:** Faça login no site [Loop Gen](https://loopgen.vercel.app/)\n\n"
                    f"**Passo 2:** Acesse o **Dashboard** e clique em **Integrar Sync Bot**\n\n"
                    f"**Passo 3:** No bot, clique em **Gerar Código** no menu acima\n\n"
                    f"**Passo 4:** Copie o código gerado e cole no modal do site (que apareceu quando você clicou em Integrar Sync Bot)\n\n"
                    f"**Passo 5:** Clique em confirmar no site e pronto! O bot e o site estão integrados.\n\n"
                    f"**Após a integração:**\n"
                    f"• Crie um projeto no site (Dashboard > Novo Projeto)\n"
                    f"• No bot, use **Definir Projeto** para selecionar o projeto criado\n"
                    f"• Agora você pode usar todas as funcionalidades da extensão!"
                )
                await inter.response.send_message(tutorial_text, ephemeral=True)

        elif custom_id == "SyncGen_ConfigSelect":
            choice = inter.values[0]

            if choice == "gen_streaming_gaming":
                await inter.response.send_modal(GenServiceModal(self))

            elif choice == "live_stock":
                await self._handle_live_stock_option(inter)

            elif choice in ["custom_embeds", "activate_gen"]:
                await inter.response.send_message(
                    f"{emoji.warn} Esta funcionalidade está em desenvolvimento e será liberada em breve!",
                    ephemeral=True
                )

        elif custom_id == "SyncGen_ProjectSelect":
            val = inter.values[0]
            key = val.replace("proj_", "")

            current_data = db.obter("database/syncgen.json")
            current_data["project_key"] = key
            db.salvar("database/syncgen.json", current_data)

            await inter.response.send_message(
                f"{emoji.correct} Projeto selecionado com sucesso! Key: `{key}`",
                ephemeral=True
            )

            # Refresh panel
            await message.wait(inter, send=False)
            components = self._build_syncgen_panel(inter)
            await inter.message.edit(components=components)

        elif custom_id == "SyncGen_LiveStockProduct":
            product_id = inter.values[0].replace("prod_", "")
            await inter.response.send_modal(LiveStockConfigModal(self, product_id))

    # ==================== HELPER METHODS ====================

    async def _generate_code(self, inter: disnake.MessageInteraction):
        """Gera código de vinculação"""
        await inter.response.defer(ephemeral=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/bot/generate-code",
                    headers={"x-bot-secret": self.bot_secret},
                    json={"discordId": str(self.bot.user.id)}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        code = data.get("code")

                        colors = db.get_document("custom_colors")
                        primary_color_hex = colors.get("primary")
                        container_kwargs = {}
                        if primary_color_hex:
                            primary_color = int(primary_color_hex.replace("#", ""), 16)
                            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

                        components = [
                            disnake.ui.Container(
                                disnake.ui.TextDisplay(
                                    f"# {emoji.link} Código de Vinculação\n\n"
                                    f"Seu código é: **`{code}`**\n\n"
                                    f"-# Acesse https://loopgen.vercel.app/ e insira este código no dashboard.\n"
                                    f"-# Após inserir o código no site, clique em **Já integrei!** abaixo."
                                ),
                                **container_kwargs,
                            ),
                            disnake.ui.ActionRow(
                                disnake.ui.Button(
                                    label="Já integrei!",
                                    style=disnake.ButtonStyle.green,
                                    emoji=emoji.correct,
                                    custom_id=f"check_code_{code}"
                                )
                            )
                        ]

                        await inter.followup.send(
                            components=components,
                            ephemeral=True
                        )
                    else:
                        await inter.followup.send(f"Erro ao gerar código: {response.status}", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Erro de conexão: {str(e)}", ephemeral=True)

    async def _show_project_selection(self, inter: disnake.MessageInteraction):
        """Mostra seleção de projetos"""
        status_data = self._get_syncgen_status()
        if not status_data.get("integrated_user_id"):
            await inter.response.send_message(
                f"{emoji.wrong} Você precisa vincular o bot a um usuário primeiro.",
                ephemeral=True
            )
            return

        await inter.response.defer()

        discord_id = status_data.get("integrated_user_id")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/projects/user/{discord_id}",
                    headers={"x-bot-secret": self.bot_secret}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        projects = data.get("projects", [])

                        if not projects:
                            await inter.followup.send(
                                f"{emoji.warn} Você não possui projetos criados no painel.\n\n"
                                f"Acesse https://loopgen.vercel.app/ e crie um novo projeto.",
                                ephemeral=True
                            )
                            return

                        options = []
                        for p in projects:
                            options.append(disnake.SelectOption(
                                label=p.get("name"),
                                value=f"proj_{p.get('key')}",
                                description=f"Key: {p.get('key')} | Uso: {p.get('usage', 0)}",
                                emoji=emoji.folder
                            ))

                        colors = db.get_document("custom_colors")
                        primary_color_hex = colors.get("primary")
                        container_kwargs = {}
                        if primary_color_hex:
                            primary_color = int(primary_color_hex.replace("#", ""), 16)
                            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

                        components = [
                            disnake.ui.Container(
                                disnake.ui.TextDisplay(
                                    f"# {emoji.z0}\n"
                                    f"-# Sync Gen > **Projetos**"
                                ),
                                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                                disnake.ui.TextDisplay(
                                    f"-# Selecione um projeto padrão para usar nas requisições."
                                ),
                                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                                disnake.ui.ActionRow(
                                    disnake.ui.StringSelect(
                                        custom_id="SyncGen_ProjectSelect",
                                        placeholder="Selecione um projeto",
                                        options=options
                                    )
                                ),
                                **container_kwargs
                            ),
                            disnake.ui.ActionRow(
                                disnake.ui.Button(
                                    label="Voltar",
                                    style=disnake.ButtonStyle.grey,
                                    emoji=emoji.back,
                                    custom_id="Extensions_SyncGen"
                                )
                            )
                        ]

                        await inter.edit_original_message(components=components)
                    else:
                        await inter.followup.send(f"Erro ao buscar projetos: {response.status}", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Erro de conexão: {str(e)}", ephemeral=True)

    async def _handle_live_stock_option(self, inter: disnake.MessageInteraction):
        """Handle Live Stock option"""
        livestock_config = self._get_livestock_config()

        if livestock_config.get("accepted_warning"):
            # User already accepted, show products
            await self._show_products_for_livestock(inter)
        else:
            # Show warning message
            colors = db.get_document("custom_colors")
            primary_color_hex = colors.get("primary")
            container_kwargs = {}
            if primary_color_hex:
                primary_color = int(primary_color_hex.replace("#", ""), 16)
                container_kwargs["accent_colour"] = disnake.Colour(primary_color)

            # Fetch auto-check services
            supported_services = []
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://loopchecker.squareweb.app/services") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            supported_services = data.get("services", [])
            except:
                pass

            services_text = ""
            if supported_services:
                services_str = ", ".join([f"**{s.capitalize()}**" for s in supported_services])
                services_text = f"Os serviços {services_str} já contam com o sistema de **auto-check** ativo.\n\n"

            components = [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(
                        f"# {emoji.warn} Aviso Importante\n\n"
                        f"{services_text}"
                        f"Para os demais serviços, a **Loop** (fornecedora desta extensão) lançará o sistema de **auto-check** "
                        f"apenas no dia **20/12/2025**.\n\n"
                        f"Por enquanto, essas contas geradas **não estão sendo verificadas automaticamente**, "
                        f"porém ainda possuem **altas possibilidades de funcionarem** devido à qualidade "
                        f"das fontes utilizadas.\n\n"
                        f"-# Deseja prosseguir mesmo sabendo desta informação?"
                    ),
                    **container_kwargs,
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Sim, prosseguir",
                        style=disnake.ButtonStyle.green,
                        emoji=emoji.correct,
                        custom_id="SyncGen_ConfirmLiveStock"
                    ),
                    disnake.ui.Button(
                        label="Cancelar",
                        style=disnake.ButtonStyle.grey,
                        emoji=emoji.wrong,
                        custom_id="SyncGen_CancelLiveStock"
                    )
                )
            ]

            await message.wait(inter, send=False)
            await inter.edit_original_message(components=components)

    async def _show_products_for_livestock(self, inter: disnake.MessageInteraction):
        """Show products for Live Stock configuration"""
        # Get products from MongoDB
        products_dict = db.get_document("loja_products") or {}

        if not products_dict:
            await inter.response.send_message(
                f"{emoji.warn} Nenhum produto encontrado. Crie produtos primeiro na loja.",
                ephemeral=True
            )
            return

        options = []
        count = 0
        for product_id, p in products_dict.items():
            if count >= 25:  # Max 25 options
                break
            product_name = p.get("name", "Sem nome")
            campos = p.get("campos", {})
            
            # ONLY show products that have at least one campo configured
            if not campos or len(campos) == 0:
                continue  # Skip products without campos
            
            if product_name:
                # Get current live stock status
                syncgen_data = self._get_syncgen_status()
                livestock = syncgen_data.get("livestock", {})
                product_config = livestock.get("products", {}).get(product_id, {})
                is_enabled = product_config.get("enabled", False)
                
                status_emoji = emoji.on if is_enabled else emoji.off
                status_text = "Ativo" if is_enabled else "Inativo"
                
                options.append(disnake.SelectOption(
                    label=product_name[:100],
                    value=f"prod_{product_id}",
                    description=f"{status_text} | Opções: {len(campos)}",
                    emoji=status_emoji
                ))
                count += 1

        if not options:
            await inter.response.send_message(
                f"{emoji.warn} Nenhum produto com opções configuradas encontrado.\n\n"
                f"**Os produtos precisam ter pelo menos uma opção para usar o Live Stock.**\n"
                f"Vá em **Loja > Produtos > [Produto] > Opções do Produto** e crie uma opção primeiro.",
                ephemeral=True
            )
            return

        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        components = [
            disnake.ui.Container(
                disnake.ui.TextDisplay(
                    f"# {emoji.z0}\n"
                    f"-# Sync Gen > **Live Stock**"
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(
                    f"Selecione um produto para configurar o reabastecimento automático.\n"
                    f"-# Apenas produtos com opções configuradas são exibidos."
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="SyncGen_LiveStockProduct",
                        placeholder="Selecione um produto",
                        options=options
                    )
                ),
                **container_kwargs
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="SyncGen_BackToConfig"
                ),
                disnake.ui.Button(
                    label="Análise",
                    style=disnake.ButtonStyle.blurple,
                    emoji=emoji.chart,
                    custom_id="SyncGen_LiveStockAnalytics"
                ),
                disnake.ui.Button(
                    label="Notificações",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.announcement if hasattr(emoji, 'announcement') else emoji.message,
                    custom_id="SyncGen_LiveStockNotifications"
                )
            )
        ]

        if hasattr(inter, 'response') and not inter.response.is_done():
            await message.wait(inter, send=False)
        await inter.edit_original_message(components=components)
    
    async def _show_livestock_analytics(self, inter: disnake.MessageInteraction):
        """Show Live Stock analytics panel"""
        syncgen_data = self._get_syncgen_status()
        livestock = syncgen_data.get("livestock", {})
        products_config = livestock.get("products", {})
        
        products_dict = db.get_document("loja_products") or {}
        
        if not products_config:
            await inter.response.send_message(
                f"{emoji.warn} Nenhum produto configurado com Live Stock ainda.",
                ephemeral=True
            )
            return
        
        # Build analytics text
        analytics_lines = []
        total_products = 0
        total_active = 0
        
        for product_id, config in products_config.items():
            product = products_dict.get(product_id, {})
            product_name = product.get("name", f"ID: {product_id}")
            
            is_enabled = config.get("enabled", False)
            service = config.get("service", "N/A")
            category = config.get("category", "N/A")
            gen_count = config.get("gen_count", 0)
            interval = config.get("interval_hours", 0)
            last_restock = config.get("last_restock", "Nunca")
            
            total_products += 1
            if is_enabled:
                total_active += 1
            
            status = f"{emoji.on}" if is_enabled else f"{emoji.off}"
            
            line = (
                f"{status} **{product_name}**\n"
                f"-# Serviço: `{service}` | Categoria: `{category}`\n"
                f"-# Gerar: `{gen_count} contas` a cada `{interval}h`\n"
                f"-# Último restock: `{last_restock[:19] if last_restock and last_restock != 'Nunca' else 'Nunca'}`"
            )
            analytics_lines.append(line)
        
        analytics_text = "\n\n".join(analytics_lines) if analytics_lines else "Nenhum produto configurado."
        
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        
        components = [
            disnake.ui.Container(
                disnake.ui.TextDisplay(
                    f"# {emoji.chart} Análise Live Stock\n"
                    f"-# {total_active}/{total_products} produtos ativos"
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(analytics_text),
                **container_kwargs
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="SyncGen_LiveStockProducts"
                )
            )
        ]
        
        if hasattr(inter, 'response') and not inter.response.is_done():
            await message.wait(inter, send=False)
        await inter.edit_original_message(components=components)
    
    async def _toggle_livestock_notifications(self, inter: disnake.MessageInteraction):
        """Toggle Live Stock DM notifications"""
        syncgen_data = db.obter("database/syncgen.json") or {}
        livestock = syncgen_data.setdefault("livestock", {})
        
        # Toggle notification setting
        current = livestock.get("dm_notifications", False)
        livestock["dm_notifications"] = not current
        
        db.salvar("database/syncgen.json", syncgen_data)
        
        new_status = "ativadas" if not current else "desativadas"
        emoji_status = emoji.on if not current else emoji.off
        
        await inter.response.send_message(
            f"{emoji_status} **Notificações de Live Stock {new_status}!**\n\n"
            f"{'Você receberá uma DM sempre que o Live Stock adicionar estoque a um produto.' if not current else 'Você não receberá mais notificações de Live Stock.'}",
            ephemeral=True
        )


# ==================== MODALS ====================

class GenServiceModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog = cog
        components = [
            disnake.ui.TextInput(
                label="Nome do Serviço",
                placeholder="Ex: Netflix, Spotify, Steam, Epic Games...",
                custom_id="service_name",
                style=disnake.TextInputStyle.short,
                max_length=50,
                required=True
            ),
            disnake.ui.Label(
                text="Categoria",
                component=disnake.ui.StringSelect(
                    placeholder="Selecione a categoria",
                    custom_id="category_select",
                    options=[
                        disnake.SelectOption(label="Streaming", value="streaming", emoji=emoji.play),
                        disnake.SelectOption(label="Gaming", value="gaming", emoji=emoji.controller),
                    ],
                    min_values=1,
                    max_values=1
                ),
                description="Selecione se é um serviço de Streaming ou Gaming.",
            ),
        ]
        super().__init__(title="Gerar Contas", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        service_name = inter.text_values["service_name"]

        # Try to get category from components
        category = "streaming"
        for component in inter.data.get("components", []):
            for child in component.get("components", []):
                if child.get("custom_id") == "category_select":
                    if "values" in child and child["values"]:
                        category = child["values"][0]

        # Check if project is configured
        data = db.obter("database/syncgen.json")
        project_key = data.get("project_key")

        if not project_key:
            await inter.response.send_message(
                f"{emoji.wrong} Nenhum projeto selecionado. Selecione um projeto nas configurações primeiro.",
                ephemeral=True
            )
            return

        await inter.response.send_message(
            f"{emoji.reload} Gerando contas de **{service_name}** ({category})...\n\n"
            f"-# Enviarei um `.txt` no seu privado quando terminar!",
            ephemeral=True
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.cog.api_url}/scrape-project",
                    headers={"x-project-key": project_key},
                    json={
                        "service": service_name,
                        "category": category,
                        "threads": 1,
                        "timeout": 600000
                    },
                    timeout=aiohttp.ClientTimeout(total=700)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        credentials = result.get("credentials", [])
                        count = len(credentials) if isinstance(credentials, list) else len(credentials.keys()) if isinstance(credentials, dict) else 0

                        if count > 0:
                            # Create file content
                            if isinstance(credentials, dict):
                                content = "\n".join([f"{email}:{password}" for email, password in credentials.items()])
                            else:
                                content = "\n".join([f"{c.get('email')}:{c.get('password')}" for c in credentials])

                            file = disnake.File(io.BytesIO(content.encode("utf-8")), filename=f"{service_name}_contas.txt")

                            try:
                                colors = db.get_document("custom_colors")
                                primary_color_hex = colors.get("primary")
                                container_kwargs = {}
                                if primary_color_hex:
                                    primary_color = int(primary_color_hex.replace("#", ""), 16)
                                    container_kwargs["accent_colour"] = disnake.Colour(primary_color)

                                components = [
                                    disnake.ui.Container(
                                        disnake.ui.TextDisplay(
                                            f"# {emoji.correct} Geração Concluída!\n\n"
                                            f"{emoji.website if hasattr(emoji, 'website') else emoji.link} **Serviço:** `{service_name}`\n"
                                            f"{emoji.folder} **Categoria:** `{category.capitalize()}`\n"
                                            f"{emoji.cart} **Quantidade:** `{count}`"
                                        ),
                                        **container_kwargs
                                    )
                                ]

                                await inter.author.send(components=components)
                                await inter.author.send(file=file)

                                await inter.edit_original_message(
                                    content=f"{emoji.correct} **Sucesso!** As contas foram enviadas no seu privado."
                                )
                            except disnake.Forbidden:
                                await inter.edit_original_message(
                                    content=f"{emoji.warn} Gerei {count} contas, mas não consegui te enviar no privado. Verifique suas configurações de privacidade."
                                )
                        else:
                            await inter.edit_original_message(
                                content=f"{emoji.warn} O processo terminou, mas nenhuma conta foi encontrada para **{service_name}**."
                            )
                    else:
                        text = await response.text()
                        try:
                            err_json = json.loads(text)
                            err_msg = err_json.get("error", text)
                        except:
                            err_msg = text
                        await inter.edit_original_message(content=f"{emoji.wrong} **Erro na API:** {response.status}\n{err_msg}")
        except asyncio.TimeoutError:
            await inter.edit_original_message(content=f"{emoji.wrong} **Timeout:** A requisição demorou muito tempo.")
        except Exception as e:
            await inter.edit_original_message(content=f"{emoji.wrong} **Erro de conexão:** {str(e)}")


class LiveStockConfigModal(disnake.ui.Modal):
    def __init__(self, cog, product_id: str):
        self.cog = cog
        self.product_id = product_id

        # Get product to check for auto-fill
        products = db.get_document("loja_products") or {}
        product = products.get(product_id, {})
        product_name = product.get("name", "")

        # Check for known streaming/gaming services in product name
        known_services = ["netflix", "spotify", "disney", "hbo", "paramount", "prime", "steam", "epic", "xbox", "playstation", "ubisoft", "ea", "origin", "crunchyroll", "funimation"]
        service_default = ""
        for service in known_services:
            if service.lower() in product_name.lower():
                service_default = service.capitalize()
                break

        # Get existing config if any
        livestock_config = cog._get_livestock_config()
        product_config = livestock_config.get("products", {}).get(product_id, {})

        components = [
            disnake.ui.TextInput(
                label="Nome do Serviço",
                placeholder="Ex: Netflix, Spotify, Steam...",
                custom_id="service_name",
                style=disnake.TextInputStyle.short,
                max_length=50,
                required=True,
                value=product_config.get("service", service_default)
            ),
            disnake.ui.TextInput(
                label="Quantas vezes gerar (máx 5)",
                placeholder="1-5",
                custom_id="gen_count",
                style=disnake.TextInputStyle.short,
                max_length=1,
                required=True,
                value=str(product_config.get("gen_count", 1))
            ),
            disnake.ui.TextInput(
                label="Intervalo de reabastecimento (horas, mín 6)",
                placeholder="6-168",
                custom_id="interval_hours",
                style=disnake.TextInputStyle.short,
                max_length=3,
                required=True,
                value=str(product_config.get("interval_hours", 6))
            ),
            disnake.ui.Label(
                text="Categoria",
                component=disnake.ui.StringSelect(
                    placeholder="Selecione a categoria",
                    custom_id="category_select",
                    options=[
                        disnake.SelectOption(label="Streaming", value="streaming", emoji=emoji.play),
                        disnake.SelectOption(label="Gaming", value="gaming", emoji=emoji.controller),
                    ],
                    min_values=1,
                    max_values=1
                ),
                description="Selecione se é um serviço de Streaming ou Gaming.",
            ),
        ]
        super().__init__(title="Configurar Live Stock", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        service_name = inter.text_values["service_name"]
        gen_count_str = inter.text_values["gen_count"]
        interval_str = inter.text_values["interval_hours"]

        # Validate gen count
        try:
            gen_count = int(gen_count_str)
            if gen_count < 1:
                gen_count = 1
            elif gen_count > 5:
                gen_count = 5
        except:
            gen_count = 1

        # Validate interval
        try:
            interval_hours = int(interval_str)
            if interval_hours < 6:
                interval_hours = 6
        except:
            interval_hours = 6

        # Get category
        category = "streaming"
        for component in inter.data.get("components", []):
            for child in component.get("components", []):
                if child.get("custom_id") == "category_select":
                    if "values" in child and child["values"]:
                        category = child["values"][0]

        # Get project key
        data = db.obter("database/syncgen.json")
        project_key = data.get("project_key")

        if not project_key:
            await inter.response.send_message(
                f"{emoji.wrong} Nenhum projeto selecionado. Configure um projeto primeiro.",
                ephemeral=True
            )
            return

        # Save config
        if "livestock" not in data:
            data["livestock"] = {}
        if "products" not in data["livestock"]:
            data["livestock"]["products"] = {}

        data["livestock"]["products"][self.product_id] = {
            "service": service_name,
            "category": category,
            "gen_count": gen_count,
            "interval_hours": interval_hours,
            "last_restock": None,
            "enabled": True
        }
        db.salvar("database/syncgen.json", data)

        await inter.response.send_message(
            f"{emoji.correct} **Live Stock configurado!**\n\n"
            f"{emoji.link} **Serviço:** `{service_name}`\n"
            f"{emoji.folder} **Categoria:** `{category}`\n"
            f"{emoji.cart} **Gerações por ciclo:** `{gen_count}`\n"
            f"{emoji.clock if hasattr(emoji, 'clock') else '⏰'} **Intervalo:** `{interval_hours} horas`\n\n"
            f"-# O reabastecimento começará em breve!",
            ephemeral=True
        )

        # Start restock task
        self.cog.bot.loop.create_task(
            run_restock_task(self.cog, self.product_id, service_name, category, gen_count, interval_hours, project_key)
        )


# ==================== RESTOCK FUNCTIONS ====================

async def run_restock_task(cog, product_id: str, service: str, category: str, gen_count: int, interval_hours: int, project_key: str):
    """Run the restock task for a product"""
    from modules.loja.cart.stock_manager import StockManager
    
    while True:
        try:
            # Check if still enabled
            data = db.obter("database/syncgen.json")
            product_config = data.get("livestock", {}).get("products", {}).get(product_id)

            if not product_config or not product_config.get("enabled"):
                print(f"[LiveStock] Task for product {product_id} stopped - disabled or not found")
                break

            # Run generation
            credentials_list = []
            for _ in range(gen_count):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{cog.api_url}/scrape-project",
                            headers={"x-project-key": project_key},
                            json={
                                "service": service,
                                "category": category,
                                "threads": 1,
                                "timeout": 300000
                            },
                            timeout=aiohttp.ClientTimeout(total=400)
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                credentials = result.get("credentials", [])
                                if isinstance(credentials, dict):
                                    for email, password in credentials.items():
                                        credentials_list.append(f"{email}:{password}")
                                elif isinstance(credentials, list):
                                    for c in credentials:
                                        credentials_list.append(f"{c.get('email')}:{c.get('password')}")
                except Exception as gen_err:
                    print(f"[LiveStock] Generation error: {gen_err}")

            # Add to product stock using StockManager
            if credentials_list:
                # Get product from MongoDB to find the first campo_id
                products = db.get_document("loja_products") or {}
                product = products.get(product_id, {})
                product_name = product.get("name", product_id)
                campos = product.get("campos", {})
                
                # Use the first campo_id if exists
                if campos:
                    campo_id = list(campos.keys())[0]
                    StockManager.add_stock_items(product_id, campo_id, credentials_list)
                    print(f"[LiveStock] Added {len(credentials_list)} items to product {product_id}, campo {campo_id}")
                    
                    # Send DM notification if enabled
                    data = db.obter("database/syncgen.json")
                    livestock = data.get("livestock", {})
                    if livestock.get("dm_notifications", False):
                        integrated_user_id = data.get("integrated_user_id")
                        if integrated_user_id and hasattr(cog, 'bot'):
                            try:
                                user = await cog.bot.fetch_user(int(integrated_user_id))
                                if user:
                                    await user.send(
                                        f"📦 **Live Stock - Estoque Adicionado!**\n\n"
                                        f"**Produto:** `{product_name}`\n"
                                        f"**Contas adicionadas:** `{len(credentials_list)}`\n"
                                        f"**Serviço:** `{service}`\n"
                                        f"**Categoria:** `{category}`\n\n"
                                        f"-# Próximo restock em {interval_hours} horas"
                                    )
                                    print(f"[LiveStock] DM notification sent to user {integrated_user_id}")
                            except Exception as dm_err:
                                print(f"[LiveStock] Failed to send DM notification: {dm_err}")

                # Update last restock time
                data = db.obter("database/syncgen.json")
                if "livestock" in data and "products" in data["livestock"] and product_id in data["livestock"]["products"]:
                    data["livestock"]["products"][product_id]["last_restock"] = disnake.utils.utcnow().isoformat()
                    db.salvar("database/syncgen.json", data)

            # Wait for next interval
            print(f"[LiveStock] Waiting {interval_hours} hours for next restock of product {product_id}")
            await asyncio.sleep(interval_hours * 3600)

        except Exception as e:
            print(f"[LiveStock] Error in restock task for product {product_id}: {e}")
            await asyncio.sleep(3600)  # Wait 1 hour on error


class LiveStockMonitor(commands.Cog):
    """Monitor Live Stock configurations and manage restock tasks"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = os.getenv("ZYNEXGEN_API_URL", "").strip().rstrip("/")
        self.active_tasks = {}  # Track active restock tasks: product_id -> task
    
    def cog_unload(self):
        self.monitor_task.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.monitor_task.is_running():
            self.monitor_task.start()
        print("[LiveStock Monitor] Starting...")
        await self._check_and_start_restocks()
    
    @tasks.loop(minutes=1)
    async def monitor_task(self):
        """Check every minute for products that need restock"""
        await self._check_and_start_restocks()
    
    @monitor_task.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()
    
    async def _check_and_start_restocks(self):
        """Check all configured Live Stock products and start tasks if needed"""
        try:
            data = db.obter("database/syncgen.json")
            if not data:
                return
            
            # Check if the extension is enabled first
            extension_enabled = data.get("enabled", True)
            if not extension_enabled:
                # If extension is disabled, cancel all active tasks and don't start new ones
                for product_id, task in list(self.active_tasks.items()):
                    task.cancel()
                    del self.active_tasks[product_id]
                return
            
            livestock = data.get("livestock", {})
            products_config = livestock.get("products", {})
            project_key = data.get("project_key")
            
            if not project_key:
                return
            
            for product_id, config in products_config.items():
                if not config.get("enabled"):
                    # Cancel task if disabled
                    if product_id in self.active_tasks:
                        self.active_tasks[product_id].cancel()
                        del self.active_tasks[product_id]
                        print(f"[LiveStock Monitor] Cancelled task for product {product_id}")
                    continue
                
                # Check if task already running
                if product_id in self.active_tasks:
                    task = self.active_tasks[product_id]
                    if not task.done():
                        continue  # Task still running
                
                # Check if it's time to restock
                last_restock = config.get("last_restock")
                interval_hours = config.get("interval_hours", 6)
                
                should_start = False
                
                if not last_restock:
                    # Never restocked, start now
                    should_start = True
                else:
                    # Check if enough time has passed
                    try:
                        from datetime import datetime
                        last_time = datetime.fromisoformat(last_restock.replace("Z", "+00:00"))
                        now = disnake.utils.utcnow()
                        hours_passed = (now - last_time).total_seconds() / 3600
                        
                        if hours_passed >= interval_hours:
                            should_start = True
                        elif hours_passed >= interval_hours - 0.1:  # Within 6 minutes of next restock
                            print(f"[LiveStock Monitor] Product {product_id} restock coming up in {int((interval_hours - hours_passed) * 60)} minutes")
                    except Exception as parse_err:
                        print(f"[LiveStock Monitor] Error parsing date for {product_id}: {parse_err}")
                        should_start = True
                
                if should_start:
                    service = config.get("service", "netflix")
                    category = config.get("category", "streaming")
                    gen_count = config.get("gen_count", 1)
                    
                    print(f"[LiveStock Monitor] Starting restock task for product {product_id}")
                    
                    # Create a temporary cog-like object for the function
                    class CogProxy:
                        def __init__(self, api_url, bot):
                            self.api_url = api_url
                            self.bot = bot
                    
                    cog_proxy = CogProxy(self.api_url, self.bot)
                    
                    task = self.bot.loop.create_task(
                        run_restock_task(cog_proxy, product_id, service, category, gen_count, interval_hours, project_key)
                    )
                    self.active_tasks[product_id] = task
        
        except Exception as e:
            print(f"[LiveStock Monitor] Error in check: {e}")


def setup(bot: commands.Bot):
    # Import tasks extension
    from disnake.ext import tasks
    bot.add_cog(ExtensionsPanel(bot))
    bot.add_cog(LiveStockMonitor(bot))

