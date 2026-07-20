import logging

import disnake
from disnake.ext import commands

from datetime import datetime
from functions.emoji import emoji
from functions.database import database as db
from functions.perms import perms
from functions.message import message, embed_message
from functions.utils import utils
from functions.plan import should_enable_panel_button
from functions.permission_matrix import has_capability
from functions.interaction_runtime import respond_error, respond_panel

logger = logging.getLogger("zynex.botconfig")
SYSTEM_BRAND = "ZYNEX Systems"

class PainelCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_salutation(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Bom dia! ☀️"
        elif 12 <= hour < 18:
            return "Boa tarde! 🌞"
        else:
            return "Boa noite! 🌙"

    def PainelComponents(self, inter: disnake.MessageInteraction, primary_color_hex: str = None, button_states: dict = None) -> list[disnake.ui.Container]:
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        # Usar estados pré-calculados dos botões se fornecidos
        if button_states is None:
            button_states = {
                "loja": should_enable_panel_button("loja"),
                "ticket": should_enable_panel_button("ticket"),
                "rendimentos": should_enable_panel_button("rendimentos"),
                "cloud": should_enable_panel_button("cloud"),
                "personalizacao": should_enable_panel_button("personalizacao"),
                "automacoes": should_enable_panel_button("automacoes"),
                "protection": should_enable_panel_button("protection"),
                "sorteios": should_enable_panel_button("sorteios"),
                "configuracoes": should_enable_panel_button("configuracoes"),
            }

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.zenyx2}"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(
                    f"Olá senhor(a) **{inter.user.name}**, {self._get_salutation()}\n"
                    "-# Aqui você pode configurar e personalizar as funcionalidades do seu ZENYX Bot."
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Configurar Loja", style=disnake.ButtonStyle.grey, emoji=emoji.cart, custom_id="Painel_Loja", disabled=not button_states["loja"]),
                    disnake.ui.Button(label="Gerenciar Ticket", style=disnake.ButtonStyle.grey, emoji=emoji.ticket, custom_id="Painel_Ticket", disabled=not button_states["ticket"]),
                    disnake.ui.Button(label="ZenyxClous", style=disnake.ButtonStyle.grey, emoji=emoji.cloud, custom_id="Painel_Cloud", disabled=not button_states["cloud"]),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Proteção do Servidor", style=disnake.ButtonStyle.grey, emoji=emoji.shield, custom_id="Painel_Protection", disabled=not button_states["protection"]),
                    disnake.ui.Button(label="Automações", style=disnake.ButtonStyle.grey, emoji=emoji.thunder, custom_id="Painel_Automacoes", disabled=not button_states["automacoes"]),
                    disnake.ui.Button(label="Configurações", style=disnake.ButtonStyle.grey, emoji=emoji.settings, custom_id="Painel_Configuracoes", disabled=not button_states["configuracoes"]),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Sorteios", style=disnake.ButtonStyle.grey, emoji=emoji.giveaway, custom_id="Painel_Sorteios", disabled=not button_states["sorteios"]),
                ),
                **container_kwargs,
            )
        ]

    def PainelEmbed(self, inter: disnake.MessageInteraction, primary_color_hex: str = None, button_states: dict = None):
        embed = disnake.Embed(
            title="ZENYX SYSTEM",
            description=f"Olá senhor(a) **{inter.user.name}**, {self._get_salutation()}\nAqui você pode configurar e personalizar as funcionalidades do seu ZENYX Bot.",
        )
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            embed.color = primary_color
        
        # Usar estados pré-calculados dos botões se fornecidos
        if button_states is None:
            button_states = {
                "loja": should_enable_panel_button("loja"),
                "ticket": should_enable_panel_button("ticket"),
                "rendimentos": should_enable_panel_button("rendimentos"),
                "cloud": should_enable_panel_button("cloud"),
                "personalizacao": should_enable_panel_button("personalizacao"),
                "automacoes": should_enable_panel_button("automacoes"),
                "protection": should_enable_panel_button("protection"),
                "sorteios": should_enable_panel_button("sorteios"),
                "configuracoes": should_enable_panel_button("configuracoes"),
            }
        
        # embed.set_footer(text=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else None)
        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Configurar Loja", style=disnake.ButtonStyle.grey, emoji=emoji.cart, custom_id="Painel_Loja", disabled=not button_states["loja"]),
                disnake.ui.Button(label="Gerenciar Ticket", style=disnake.ButtonStyle.grey, emoji=emoji.ticket, custom_id="Painel_Ticket", disabled=not button_states["ticket"]),
                disnake.ui.Button(label="ZenyxClous", style=disnake.ButtonStyle.grey, emoji=emoji.cloud, custom_id="Painel_Cloud", disabled=not button_states["cloud"]),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Proteção do Servidor", style=disnake.ButtonStyle.grey, emoji=emoji.shield, custom_id="Painel_Protection", disabled=not button_states["protection"]),
                disnake.ui.Button(label="Automações", style=disnake.ButtonStyle.grey, emoji=emoji.thunder, custom_id="Painel_Automacoes", disabled=not button_states["automacoes"]),
                disnake.ui.Button(label="Configurações", style=disnake.ButtonStyle.grey, emoji=emoji.settings, custom_id="Painel_Configuracoes", disabled=not button_states["configuracoes"]),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Sorteios", style=disnake.ButtonStyle.grey, emoji=emoji.giveaway, custom_id="Painel_Sorteios", disabled=not button_states["sorteios"]),
            ),
        ]
        return embed, components

    @commands.slash_command(
        name="botconfig",
        description="💰 | Vendas e Moderação | Configurar as opções do bot.",
        guild_ids=[utils.obter_server_principal()],
    )
    async def botconfig(self, inter: disnake.ApplicationCommandInteraction):
        """Abre o painel imediatamente, sem deixar uma mensagem de carregamento presa."""
        try:
            if not await perms.check(inter):
                await respond_error(inter, "Você não tem permissão para usar este comando.")
                return

            mode_data = db.get_document("custom_mode") or {}
            mode = mode_data.get("mode", "components")
            colors = db.get_document("custom_colors") or {}
            primary_color_hex = colors.get("primary")

            button_states = {
                "loja": should_enable_panel_button("loja"),
                "ticket": should_enable_panel_button("ticket"),
                "rendimentos": should_enable_panel_button("rendimentos"),
                "cloud": should_enable_panel_button("cloud"),
                "personalizacao": should_enable_panel_button("personalizacao"),
                "automacoes": should_enable_panel_button("automacoes"),
                "protection": should_enable_panel_button("protection"),
                "sorteios": should_enable_panel_button("sorteios"),
                "configuracoes": should_enable_panel_button("configuracoes"),
            }

            if mode == "embed":
                embed, components = self.PainelEmbed(inter, primary_color_hex, button_states)
                panel = {"embed": embed, "components": components}
            else:
                panel = {"components": self.PainelComponents(inter, primary_color_hex, button_states)}

            await respond_panel(inter, panel, ephemeral=True)
        except Exception as exc:
            logger.exception("Falha ao abrir /botconfig")
            await respond_error(
                inter,
                "Não foi possível abrir o painel. O erro foi registrado no console do bot.",
            )

    @commands.Cog.listener("on_button_click")
    async def Painel_Button_Listener(self, inter: disnake.MessageInteraction):
        custom_id = getattr(inter.component, "custom_id", "") or ""
        if not custom_id.startswith("Painel"):
            return

        try:
            if custom_id == "PainelInicial":
                mode_data = db.get_document("custom_mode") or {}
                mode = mode_data.get("mode", "components")
                colors = db.get_document("custom_colors") or {}
                primary_color_hex = colors.get("primary")
                button_states = {
                    "loja": should_enable_panel_button("loja"),
                    "ticket": should_enable_panel_button("ticket"),
                    "rendimentos": should_enable_panel_button("rendimentos"),
                    "cloud": should_enable_panel_button("cloud"),
                    "personalizacao": should_enable_panel_button("personalizacao"),
                    "automacoes": should_enable_panel_button("automacoes"),
                    "protection": should_enable_panel_button("protection"),
                    "sorteios": should_enable_panel_button("sorteios"),
                    "configuracoes": should_enable_panel_button("configuracoes"),
                }
                if mode == "embed":
                    embed, components = self.PainelEmbed(inter, primary_color_hex, button_states)
                    panel = {"embed": embed, "components": components}
                else:
                    panel = {"components": self.PainelComponents(inter, primary_color_hex, button_states)}
                return await respond_panel(inter, panel, prefer_edit=True)

            if custom_id == "Painel_Loja":
                store_cog = self.bot.get_cog("Loja")
                if store_cog is None:
                    return await respond_error(inter, "O módulo Configurar Loja não foi carregado neste plano.")
                return await store_cog.display_store_panel(inter)

            if custom_id == "Painel_Configuracoes":
                settings_cog = self.bot.get_cog("Settings")
                if settings_cog is None:
                    return await respond_error(inter, "O módulo Configurações não foi carregado neste plano.")
                return await settings_cog.display_settings_panel(inter)

            if custom_id == "Painel_Protection":
                if not await perms.check_owner(inter):
                    return await respond_error(
                        inter,
                        "Apenas o proprietário do bot ou do servidor pode acessar esta funcionalidade.",
                    )
                protection_cog = self.bot.get_cog("ProtectionCog")
                if protection_cog is None:
                    return await respond_error(inter, "O módulo Proteção do Servidor não está disponível.")
                return await protection_cog.display_protection_panel(inter)

            if custom_id == "Painel_Automacoes":
                automations_cog = self.bot.get_cog("AutomationModulesCog")
                if automations_cog is None:
                    return await respond_error(inter, "O módulo Automações não está disponível.")
                return await automations_cog.display_automations_panel(inter)

            if custom_id == "Painel_Ticket":
                if not has_capability(inter, "tickets"):
                    return await respond_error(inter, "Você não possui permissão para gerenciar tickets.")
                ticket_cog = self.bot.get_cog("TicketConfigCog")
                if ticket_cog is None:
                    return await respond_error(inter, "O módulo Gerenciar Ticket não está disponível.")
                return await ticket_cog.display_ticket_panel(inter)

            if custom_id == "Painel_Sorteios":
                giveaways_cog = self.bot.get_cog("Giveaways")
                if giveaways_cog is None:
                    return await respond_error(inter, "O módulo Sorteios não está disponível.")
                return await giveaways_cog.display_giveaways_panel(inter)

            if custom_id == "Painel_Cloud":
                cloud_cog = self.bot.get_cog("Cloud")
                if cloud_cog is None:
                    return await respond_error(inter, "O módulo ZenyxClous não está disponível.")
                return await cloud_cog.display_cloud_panel(inter)

            if custom_id == "Painel_Rendimentos":
                rendimentos_cog = self.bot.get_cog("RendimentosSystem")
                if rendimentos_cog is None:
                    return await respond_error(inter, "O módulo de rendimentos não está disponível.")
                mode = (db.get_document("custom_mode") or {}).get("mode", "components")
                panel_data = rendimentos_cog.panel(inter)
                if mode == "embed":
                    embed, components = panel_data
                    return await respond_panel(
                        inter,
                        {"embed": embed, "components": components},
                        prefer_edit=True,
                    )
                return await respond_panel(inter, panel_data, prefer_edit=True)

            return await respond_error(inter, "Este botão ainda não possui uma rota válida.")
        except Exception:
            logger.exception("Falha ao processar botão principal | custom_id=%s", custom_id)
            return await respond_error(
                inter,
                "Não foi possível abrir esta seção. Consulte o erro exibido no console do bot.",
            )

def setup(bot: commands.Bot):
    bot.add_cog(PainelCommand(bot))