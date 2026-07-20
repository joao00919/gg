import disnake
from disnake.ext import commands

from functions.emoji import emoji
from functions.database import database as db
from functions.message import message, embed_message
from functions.interaction_runtime import respond_panel

class ProtectionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def PainelComponents(inter: disnake.MessageInteraction) -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > **Proteção**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay("Gerencie as opções de proteção do servidor.\nEscolha uma das opções abaixo para configurar:"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="Protecao_Select",
                        placeholder="Selecione uma seção para configurar",
                        options=[
                            disnake.SelectOption(label="Proteção Geral", value="geral", emoji=emoji.shield, description="Configure links, canais, cargos, banimentos e expulsões"),
                            disnake.SelectOption(label="Backup e Restauração", value="backup", emoji=getattr(emoji, "save", "💾"), description="Faça backup e restaure a estrutura do servidor"),
                            disnake.SelectOption(label="Privatizações", value="privatizacoes", emoji=emoji.lock, description="Defina regras de privatização de canais"),
                            disnake.SelectOption(label="Permissões Internas", value="permissoes_internas", emoji=emoji.role, description="Configure permissões internas do sistema"),
                        ],
                    )
                ),
                **container_kwargs
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="PainelInicial"),
            )
        ]

    @staticmethod
    def PainelEmbed(inter: disnake.MessageInteraction):
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        embed = disnake.Embed(
            title=f"Painel de Proteção",
            description="Gerencie as opções de proteção do servidor.\nEscolha uma das opções abaixo para configurar:",
        )
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            embed.color = primary_color

        components = [
            disnake.ui.ActionRow(
                disnake.ui.StringSelect(
                    custom_id="Protecao_Select",
                    placeholder="Selecione uma seção para configurar",
                    options=[
                        disnake.SelectOption(label="Proteção Geral", value="geral", emoji=emoji.shield, description="Configure links, canais, cargos, banimentos e expulsões"),
                        disnake.SelectOption(label="Backup e Restauração", value="backup", emoji=getattr(emoji, "save", "💾"), description="Faça backup e restaure a estrutura do servidor"),
                        disnake.SelectOption(label="Privatizações", value="privatizacoes", emoji=emoji.lock, description="Defina regras de privatização de canais"),
                        disnake.SelectOption(label="Permissões Internas", value="permissoes_internas", emoji=emoji.role, description="Configure permissões internas do sistema"),
                    ],
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="PainelInicial"),
            )
        ]
        return embed, components

    async def display_protection_panel(self, inter: disnake.MessageInteraction):
        """Exibe o painel principal de proteção sem deixar o clique expirar."""
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            embed, components = self.PainelEmbed(inter)
            panel = {"embed": embed, "components": components}
        else:
            panel = {"components": self.PainelComponents(inter)}
        return await respond_panel(inter, panel, prefer_edit=True)

    @commands.Cog.listener("on_button_click")
    async def protection_button_listener(self, inter: disnake.MessageInteraction):
        """Ouve os cliques nos botões do painel de proteção e seus subpainéis."""
        custom_id = inter.component.custom_id

        if custom_id not in [
            "Protecao_Geral", 
            "Protecao_Privatizacoes", 
            "Back_To_Protection_Panel"
        ]:
            return

        try:
            if not inter.response.is_done():
                await inter.response.defer()
        except disnake.errors.NotFound:
            return

        if custom_id == "Protecao_Geral":
            protecao_geral_cog = self.bot.get_cog("ProtectionGeralCog")
            if protecao_geral_cog:
                await protecao_geral_cog.display_protecao_geral_panel(inter)

        if custom_id == "Protecao_Privatizacoes":
            privatizacoes_cog = self.bot.get_cog("PrivatizacoesCog")
            if privatizacoes_cog:
                await privatizacoes_cog.display_privatizacoes_panel(inter)

        if custom_id == "Back_To_Protection_Panel":
            await self.display_protection_panel(inter)

    @commands.Cog.listener("on_dropdown")
    async def protection_dropdown_listener(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Protecao_Select":
            choice = inter.values[0]

            if choice == "geral":
                protecao_geral_cog = self.bot.get_cog("ProtectionGeralCog")
                if protecao_geral_cog:
                    await protecao_geral_cog.display_protecao_geral_panel(inter)
                return

            if choice == "backup":
                backup_cog = self.bot.get_cog("Backup")
                if backup_cog:
                    return await backup_cog.display_backup_panel(inter)
                return await inter.response.send_message(f"{emoji.wrong} Módulo de backup indisponível neste plano.", ephemeral=True)

            if choice == "privatizacoes":
                privatizacoes_cog = self.bot.get_cog("PrivatizacoesCog")
                if privatizacoes_cog:
                    await privatizacoes_cog.display_privatizacoes_panel(inter)
                return

            if choice == "permissoes_internas":
                cog = self.bot.get_cog("PermsInternasCog") or self.bot.get_cog("PermissoesInternasCog")
                if cog and hasattr(cog, "display_panel"):
                    return await cog.display_panel(inter)
                return await inter.response.send_message(f"{emoji.warn} Módulo de permissões internas indisponível.", ephemeral=True)

def setup(bot: commands.Bot):
    bot.add_cog(ProtectionCog(bot))