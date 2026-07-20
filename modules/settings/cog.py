from disnake.ext import commands
import disnake

from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
from functions.perms import perms
from functions.interaction_runtime import respond_panel, respond_error


class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _options():
        return [
            disnake.SelectOption(label="Moderação", value="moderacao", emoji=emoji.swords, description="Configurar sistemas de moderação"),
            disnake.SelectOption(label="Notificações", value="notificacoes", emoji=emoji.warn, description="Configurar sistemas de notificação"),
            disnake.SelectOption(label="Configurar Bot", value="configurar_bot", emoji=emoji.config, description="Configurar opções do bot"),
            disnake.SelectOption(label="Configurar Mensagens", value="mensagens", emoji=getattr(emoji, "speech", emoji.textc), description="Configurar canais de logs e mensagens automáticas"),
            disnake.SelectOption(label="Configurar Canais", value="canais", emoji=emoji.textc, description="Configurar canais do servidor"),
            disnake.SelectOption(label="Configurar Cargos", value="cargos", emoji=emoji.role, description="Configurar cargos do servidor"),
        ]

    def settings_components(self, inter: disnake.MessageInteraction) -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors") or {}
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > **Configurações**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "Configure e personalize os canais, cargos e formas de pagamento.\n"
                    "Selecione uma seção abaixo para configurar."
                ),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="Configuracoes_Select",
                        placeholder="Selecione uma opção para configurar",
                        options=self._options(),
                    )
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Formas de Pagamento",
                        style=disnake.ButtonStyle.grey,
                        emoji=emoji.dollar,
                        custom_id="Configuracoes_Pagamentos",
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="PainelInicial")
            ),
        ]

    def settings_embed(self, inter: disnake.MessageInteraction):
        colors = db.get_document("custom_colors") or {}
        embed = disnake.Embed(
            title="Configurações",
            description="Configure e personalize os canais, cargos e formas de pagamento.\nSelecione uma seção abaixo para configurar.",
        )
        if colors.get("primary"):
            embed.color = int(colors["primary"].replace("#", ""), 16)
        components = [
            disnake.ui.ActionRow(
                disnake.ui.StringSelect(
                    custom_id="Configuracoes_Select",
                    placeholder="Selecione uma opção para configurar",
                    options=self._options(),
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Formas de Pagamento", style=disnake.ButtonStyle.grey, emoji=emoji.dollar, custom_id="Configuracoes_Pagamentos")
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="PainelInicial")
            ),
        ]
        return embed, components

    async def display_settings_panel(self, inter: disnake.MessageInteraction):
        """Abre Configurações reconhecendo o clique imediatamente."""
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            embed, components = self.settings_embed(inter)
            panel = {"embed": embed, "components": components}
        else:
            panel = {"components": self.settings_components(inter)}
        return await respond_panel(inter, panel, prefer_edit=True)

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id != "Configuracoes_Select":
            return
        choice = inter.values[0]
        reference = self.bot.get_cog("SettingsReferenceCog")
        if reference:
            return await reference.show(inter, choice)
        return await respond_error(inter, "Módulo de configurações indisponível.")


def setup(bot: commands.Bot):
    bot.add_cog(Settings(bot))
