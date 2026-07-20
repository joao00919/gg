import disnake
import asyncio
from disnake.ext import commands
from functions.emoji import emoji
from functions.database import database as db
from functions.perms import perms
from functions.message import message, embed_message
from functions.utils import utils


class ConectarCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._reconnect_attempted = False

    def _get_connection_status(self, guild_id: int = None) -> dict:
        """Obtém o status atual de conexão do bot"""
        connection_data = db.get_document("bot_connection") or {}
        channel_id = connection_data.get("channel_id")
        
        channel = None
        if channel_id:
            channel = self.bot.get_channel(int(channel_id))
        
        is_connected = False
        if channel and self.bot.voice_clients:
            for vc in self.bot.voice_clients:
                if vc.channel and vc.channel.id == int(channel_id):
                    # Se guild_id foi fornecido, verificar se é do mesmo servidor
                    if guild_id is None or vc.guild.id == guild_id:
                        is_connected = True
                        break
        
        return {
            "channel_id": channel_id,
            "channel": channel,
            "is_connected": is_connected
        }

    def ConectarComponents(self, inter: disnake.MessageInteraction) -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        connection = self._get_connection_status(inter.guild.id if inter.guild else None)
        channel = connection["channel"]
        is_connected = connection["is_connected"]

        channel_display = channel.mention if channel else "`Nenhum canal configurado`"

        connect_button_label = "Desconectar" if is_connected else "Conectar"
        connect_button_style = disnake.ButtonStyle.red if is_connected else disnake.ButtonStyle.green
        connect_button_emoji = emoji.voice

        container = disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {emoji.z0}\n-# **Gerenciar Conexão do Bot**"),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            disnake.ui.TextDisplay(
                f"{emoji.voice} **Canal Atual:** {channel_display}"
            ),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label=connect_button_label,
                    style=connect_button_style,
                    emoji=connect_button_emoji,
                    custom_id="Conectar_Toggle"
                ),
                disnake.ui.Button(
                    label="Editar Canal",
                    style=disnake.ButtonStyle.blurple,
                    emoji=emoji.edit,
                    custom_id="Conectar_EditChannel"
                ),
            ),
            **container_kwargs
        )

        return [container]

    def ConectarEmbed(self, inter: disnake.MessageInteraction):
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        connection = self._get_connection_status(inter.guild.id if inter.guild else None)
        channel = connection["channel"]
        is_connected = connection["is_connected"]

        channel_display = channel.mention if channel else "`Nenhum canal configurado`"

        embed = disnake.Embed(
            title=f"{emoji.z0} Gerenciar Conexão do Bot",
            description=f"{emoji.voice} **Canal Atual:** {channel_display}",
        )
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            embed.color = primary_color

        connect_button_label = "Desconectar" if is_connected else "Conectar"
        connect_button_style = disnake.ButtonStyle.red if is_connected else disnake.ButtonStyle.green
        connect_button_emoji = emoji.voice

        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label=connect_button_label,
                    style=connect_button_style,
                    emoji=connect_button_emoji,
                    custom_id="Conectar_Toggle"
                ),
                disnake.ui.Button(
                    label="Editar Canal",
                    style=disnake.ButtonStyle.blurple,
                    emoji=emoji.edit,
                    custom_id="Conectar_EditChannel"
                ),
            )
        ]
        return embed, components

    @commands.slash_command(
        name="conectar",
        description="🛠️ | Vendas Moderação | Faz o bot entrar em um canal de voz",
        guild_ids=[utils.obter_server_principal()],
    )
    async def conectar(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)
        
        if not await perms.check(inter):
            await inter.followup.send("Você não tem permissão para usar este comando", ephemeral=True)
            return

        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            embed, components = self.ConectarEmbed(inter)
            await inter.edit_original_response(content=None, embed=embed, components=components)
        else:
            await inter.edit_original_response(
                components=self.ConectarComponents(inter),
            )

    @commands.Cog.listener("on_button_click")
    async def Conectar_Button_Listener(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id.startswith("Conectar"):
            return

        custom_id = inter.component.custom_id

        if custom_id == "Conectar_Toggle":
            await self._handle_toggle_connection(inter)
        elif custom_id == "Conectar_EditChannel":
            await self._handle_edit_channel(inter)

    async def _handle_toggle_connection(self, inter: disnake.MessageInteraction):
        """Conecta ou desconecta o bot do canal de voz"""
        await inter.response.defer(ephemeral=True)
        
        connection = self._get_connection_status(inter.guild.id if inter.guild else None)
        channel_id = connection["channel_id"]
        is_connected = connection["is_connected"]

        if not channel_id:
            await inter.followup.send("Configure um canal primeiro usando o botão 'Editar Canal'", ephemeral=True)
            return

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            await inter.followup.send("Canal não encontrado. Configure um novo canal.", ephemeral=True)
            return

        if not isinstance(channel, disnake.VoiceChannel):
            await inter.followup.send("O canal configurado não é um canal de voz.", ephemeral=True)
            return

        try:
            if is_connected:
                # Desconectar
                voice_client = None
                for vc in self.bot.voice_clients:
                    if vc.channel and vc.channel.id == channel.id:
                        voice_client = vc
                        break
                
                if voice_client:
                    await voice_client.disconnect()
                
                # Salvar estado de desconexão
                connection_data = db.get_document("bot_connection") or {}
                connection_data["was_connected"] = False
                db.save_document("bot_connection", connection_data)
            else:
                # Verificar se já está conectado em outro canal e desconectar de todos
                if self.bot.voice_clients:
                    for vc in self.bot.voice_clients:
                        if vc.channel:
                            await vc.disconnect()
                
                # Conectar ao canal
                await channel.connect()
                
                # Salvar estado de conexão
                connection_data = db.get_document("bot_connection") or {}
                connection_data["was_connected"] = True
                db.save_document("bot_connection", connection_data)
        except Exception as e:
            error_msg = str(e)
            if "PyNaCl" in error_msg:
                await inter.followup.send("Erro ao conectar: É necessário instalar a biblioteca PyNaCl. Execute: `pip install PyNaCl`", ephemeral=True)
            else:
                await inter.followup.send(f"Erro ao {'desconectar' if is_connected else 'conectar'}: {error_msg}", ephemeral=True)
            return

        # Atualizar painel
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            embed, components = self.ConectarEmbed(inter)
            await inter.edit_original_message(content=None, embed=embed, components=components)
        else:
            await inter.edit_original_message(components=self.ConectarComponents(inter))

    async def _handle_edit_channel(self, inter: disnake.MessageInteraction):
        """Abre seleção de canal de voz"""
        await inter.response.defer(ephemeral=True)
        
        # Criar select de canais de voz
        voice_channels = [ch for ch in inter.guild.channels if isinstance(ch, disnake.VoiceChannel)]
        
        if not voice_channels:
            await inter.followup.send("Não há canais de voz neste servidor.", ephemeral=True)
            return
        
        mode = db.get_document("custom_mode").get("mode")

        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        select_options = [
            disnake.SelectOption(
                label=ch.name,
                value=str(ch.id),
                description=f"ID: {ch.id}"
            )
            for ch in voice_channels[:25]  # Limite do Discord
        ]

        if mode == "components":
            container_kwargs = {}
            if primary_color_hex:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

            container = disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# **Selecionar Canal de Voz**"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(f"{emoji.information} Selecione o canal de voz onde o bot deve se conectar:"),
                disnake.ui.ActionRow(
                    disnake.ui.ChannelSelect(
                        placeholder="Selecione um canal de voz...",
                        custom_id="Conectar_SelectChannel",
                        channel_types=[disnake.ChannelType.voice],
                        min_values=1,
                        max_values=1,
                    )
                ),
                **container_kwargs
            )
            await inter.edit_original_message(components=[container])
        else:
            embed_kwargs = {}
            if primary_color_hex:
                embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

            embed = disnake.Embed(
                title=f"{emoji.z0} Selecionar Canal de Voz",
                description=f"{emoji.information} Selecione o canal de voz onde o bot deve se conectar:",
                **embed_kwargs
            )

            components = [
                disnake.ui.ActionRow(
                    disnake.ui.ChannelSelect(
                        placeholder="Selecione um canal de voz...",
                        custom_id="Conectar_SelectChannel",
                        channel_types=[disnake.ChannelType.voice],
                        min_values=1,
                        max_values=1,
                    )
                )
            ]
            await inter.edit_original_message(content=None, embed=embed, components=components)

    @commands.Cog.listener("on_dropdown")
    async def Conectar_Dropdown_Listener(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Conectar_SelectChannel":
            await inter.response.defer(ephemeral=True)
            
            channel_id = int(inter.values[0])
            channel = inter.guild.get_channel(channel_id)

            if not channel or not isinstance(channel, disnake.VoiceChannel):
                await inter.followup.send("Canal inválido.", ephemeral=True)
                return

            # Salvar canal
            connection_data = db.get_document("bot_connection") or {}
            connection_data["channel_id"] = str(channel_id)
            db.save_document("bot_connection", connection_data)

            # Atualizar painel
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                embed, components = self.ConectarEmbed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await inter.edit_original_message(components=self.ConectarComponents(inter))

    @commands.Cog.listener("on_ready")
    async def auto_reconnect(self):
        """Reconecta automaticamente o bot ao canal de voz se estava conectado antes"""
        # Evitar múltiplas execuções
        if self._reconnect_attempted:
            return
        
        self._reconnect_attempted = True
        
        connection_data = db.get_document("bot_connection") or {}
        was_connected = connection_data.get("was_connected", False)
        channel_id = connection_data.get("channel_id")
        
        if not was_connected or not channel_id:
            return
        
        # Aguardar um pouco para garantir que o bot está completamente pronto
        await asyncio.sleep(2)
        
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel or not isinstance(channel, disnake.VoiceChannel):
                # Canal não encontrado ou inválido, limpar estado
                connection_data["was_connected"] = False
                db.save_document("bot_connection", connection_data)
                return
            
            # Verificar se já está conectado
            is_already_connected = False
            if self.bot.voice_clients:
                for vc in self.bot.voice_clients:
                    if vc.channel and vc.channel.id == channel.id:
                        is_already_connected = True
                        break
            
            if not is_already_connected:
                # Conectar ao canal
                await channel.connect()
                
                print(f"[Conectar] Bot reconectado automaticamente ao canal {channel.name} ({channel.id})")
        except Exception as e:
            # Se falhar ao reconectar, limpar estado
            connection_data["was_connected"] = False
            db.save_document("bot_connection", connection_data)
            print(f"[Conectar] Erro ao reconectar automaticamente: {e}")


def setup(bot: commands.Bot):
    bot.add_cog(ConectarCommand(bot))
