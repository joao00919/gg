import disnake
from disnake.ext import commands
from functions.emoji import emoji
from functions.message import message, embed_message
from functions.database import database as db
from . import helpers

class MensagensModal(disnake.ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        config = helpers.carregar_config()
        
        # Placeholder simplificado devido ao limite de 100 caracteres do Discord
        # Variáveis: {member}, {membername}, {inviter}, {invitername}, {invites}, {entry_mode}
        
        components = [
            disnake.ui.TextInput(
                label="Mensagem de Entrada (Normal)",
                custom_id="mensagem_entrada",
                style=disnake.TextInputStyle.paragraph,
                required=False,
                max_length=2000,
                placeholder="Variáveis: {member}, {membername}, {inviter}, {invitername}, {invites}, {entry_mode}.",
                value=config.get("welcome_message", ""),
            ),
            disnake.ui.TextInput(
                label="Mensagem de Entrada (Vanity URL)",
                custom_id="mensagem_entrada_vanity",
                style=disnake.TextInputStyle.paragraph,
                required=False,
                max_length=2000,
                placeholder="Variáveis: {member}, {membername}, {inviter}, {invitername}, {invites}, {entry_mode}",
                value=config.get("welcome_message_vanity", ""),
            ),
            disnake.ui.TextInput(
                label="Mensagem de Saída",
                custom_id="mensagem_saida",
                style=disnake.TextInputStyle.paragraph,
                required=False,
                max_length=2000,
                placeholder="Variáveis: {member}, {membername}, {inviter}, {invitername}, {invites}, {entry_mode}",
                value=config.get("leave_message", ""),
            ),
        ]
        super().__init__(title="Configurar Mensagens do Invite Tracker", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(with_message=False)
        
        config = helpers.carregar_config()
        # Salvar as mensagens (podem estar vazias para desativar)
        config["welcome_message"] = inter.text_values.get("mensagem_entrada", "").strip()
        config["welcome_message_vanity"] = inter.text_values.get("mensagem_entrada_vanity", "").strip()
        config["leave_message"] = inter.text_values.get("mensagem_saida", "").strip()
        helpers.salvar_config(config)

        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            embed, components = InviteTrackerCog.PainelEmbed(self.bot)
            await inter.edit_original_message(content=None, embed=embed, components=components)
        else:
            await inter.edit_original_message(components=InviteTrackerCog.Painel(self.bot))


class InviteTrackerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def Painel(bot: commands.Bot) -> list[disnake.ui.Container]:
        config = helpers.carregar_config()
        ativado = config.get("ativado", False)
        channel_id = config.get("channel_id")
        
        channel = bot.get_channel(channel_id) if channel_id else "Não definido"

        resumo = (
            f"{emoji.on if ativado else emoji.off} **Status:** `{'Ativado' if ativado else 'Desativado'}`\n"
            f"{emoji.message} **Canal:** {channel.mention if isinstance(channel, disnake.TextChannel) else '`Não definido`'}\n"
        )

        botoes = [
            disnake.ui.Button(
                label="",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.power,
                custom_id="InviteTracker_ToggleAtivo"
            ),
            disnake.ui.Button(
                label="Definir Canal",
                style=disnake.ButtonStyle.blurple,
                emoji=emoji.message,
                custom_id="InviteTracker_DefinirCanal",
                disabled=not ativado
            ),
            disnake.ui.Button(
                label="Configurar Mensagens",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.message,
                custom_id="InviteTracker_ConfigurarMensagens",
                disabled=not ativado
            ),
        ]

        primary_color_hex = db.get_document("custom_colors").get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"""
# {emoji.z0}
-# Painel > Automações > **Invite Tracker**
                """),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(resumo),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(botoes[0], botoes[1]),
                disnake.ui.ActionRow(botoes[2]),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarAutomações"),
            )
        ]

    @staticmethod
    def PainelEmbed(bot: commands.Bot) -> tuple[disnake.Embed, list[disnake.ui.ActionRow]]:
        config = helpers.carregar_config()
        ativado = config.get("ativado", False)
        channel_id = config.get("channel_id")
        
        channel = bot.get_channel(channel_id) if channel_id else "Não definido"

        resumo = (
            f"{emoji.on if ativado else emoji.off} **Status:** `{'Ativado' if ativado else 'Desativado'}`\n"
            f"{emoji.message} **Canal:** {channel.mention if isinstance(channel, disnake.TextChannel) else '`Não definido`'}\n"
        )
        
        if ativado:
            resumo += (
                f"\n**Variáveis disponíveis:**\n"
                f"• `{{member}}` - Menção do membro\n"
                f"• `{{membername}}` - Nome de exibição\n"
                f"• `{{inviter}}` - Menção do convidador\n"
                f"• `{{invitername}}` - Nome do convidador\n"
                f"• `{{invites}}` - Total de convites válidos\n"
                f"• `{{entry_mode}}` - Modo de entrada (Convite ou Vanity Url)"
            )

        primary_color_hex = db.get_document("custom_colors").get("primary")
        embed = disnake.Embed(
            title=f"Invite Tracker",
            description="Monitore os convites do seu servidor e envie mensagens de boas-vindas e saída."
        )
        if primary_color_hex:
            embed.color = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
        
        embed.add_field(name="Configurações", value=resumo, inline=False)

        botoes = [
            disnake.ui.Button(
                label="",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.power,
                custom_id="InviteTracker_ToggleAtivo"
            ),
            disnake.ui.Button(
                label="Definir Canal",
                style=disnake.ButtonStyle.blurple,
                emoji=emoji.message,
                custom_id="InviteTracker_DefinirCanal",
                disabled=not ativado
            ),
            disnake.ui.Button(
                label="Configurar Mensagens",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.message,
                custom_id="InviteTracker_ConfigurarMensagens",
                disabled=not ativado
            ),
        ]

        components = [
            disnake.ui.ActionRow(botoes[0], botoes[1]),
            disnake.ui.ActionRow(botoes[2]),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarAutomações"),
            )
        ]
        return embed, components

    @staticmethod
    def PainelCanal() -> list[disnake.ui.Container]:
        primary_color_hex = db.get_document("custom_colors").get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"""
# {emoji.z0}
-# Painel > Automações > Invite Tracker > **Definir Canal**
                """),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay("Selecione o canal para enviar as mensagens de entrada e saída."),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.ChannelSelect(
                        custom_id="InviteTracker_SelectCanal",
                        placeholder="Selecione um canal de texto",
                        channel_types=[disnake.ChannelType.text],
                        min_values=1,
                        max_values=1,
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="InviteTracker_Voltar"),
            )
        ]

    @staticmethod
    def PainelCanalEmbed() -> tuple[disnake.Embed, list[disnake.ui.ActionRow]]:
        primary_color_hex = db.get_document("custom_colors").get("primary")
        embed = disnake.Embed(
            title=f"Invite Tracker > Definir Canal",
            description="Selecione o canal para enviar as mensagens de entrada e saída."
        )
        if primary_color_hex:
            embed.color = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
            
        components = [
            disnake.ui.ActionRow(
                disnake.ui.ChannelSelect(
                    custom_id="InviteTracker_SelectCanal",
                    placeholder="Selecione um canal de texto",
                    channel_types=[disnake.ChannelType.text],
                    min_values=1,
                    max_values=1,
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="InviteTracker_Voltar"),
            )
        ]
        return embed, components

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        cid = inter.component.custom_id
        if not cid.startswith("InviteTracker_"):
            return

        if cid == "InviteTracker_ConfigurarMensagens":
            await inter.response.send_modal(MensagensModal(bot=self.bot))
            return

        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter, send=False)
        else:
            await inter.response.defer(with_message=False)
            await message.wait(inter, send=False)

        if cid == "InviteTracker_ToggleAtivo":
            config = helpers.carregar_config()
            config["ativado"] = not config.get("ativado", False)
            helpers.salvar_config(config)
            if mode == "embed":
                embed, components = self.PainelEmbed(inter.bot)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await inter.edit_original_message(components=self.Painel(inter.bot))
        elif cid == "InviteTracker_DefinirCanal":
            if mode == "embed":
                embed, components = self.PainelCanalEmbed()
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await inter.edit_original_message(components=self.PainelCanal())
        elif cid == "InviteTracker_Voltar":
            if mode == "embed":
                embed, components = self.PainelEmbed(self.bot)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await inter.edit_original_message(components=self.Painel(self.bot))

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        if inter.data.custom_id == "InviteTracker_SelectCanal":
            channel_id = int(inter.values[0])
            
            config = helpers.carregar_config()
            config["channel_id"] = channel_id
            helpers.salvar_config(config)
            
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter)
                embed, components = self.PainelEmbed(inter.bot)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await inter.response.defer(with_message=False)
                await message.wait(inter, send=False)
                await inter.edit_original_message(components=self.Painel(inter.bot))

    # Removido: cache_invites - não é mais necessário pois o tsk_invite_tracker.py gerencia o cache
    
    # Removido: on_member_join duplicado
    # O listener de entrada está implementado em tasks/automations/tsk_invite_tracker.py
    # que também gerencia as estatísticas de convites e é mais preciso

    # Removido: on_member_remove duplicado
    # O listener de saída está implementado em tasks/automations/tsk_invite_tracker.py
    # que também gerencia as estatísticas de convites

def setup(bot: commands.Bot):
    bot.add_cog(InviteTrackerCog(bot))
