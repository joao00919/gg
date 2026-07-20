import disnake
from disnake.ext import commands

from functions.emoji import emoji
from functions.message import message
from .builder import Builder
from .anunciar import Anunciar

class Enviar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def send_to_channel(channel: disnake.TextChannel) -> disnake.Message:
        built = Builder.build()
        if built["mode"] == "v2":
            message =await channel.send(
                components=built["components"],
                flags=built["flags"],
                allowed_mentions=disnake.AllowedMentions.none(),
            )
        else:
            message = await channel.send(
                content=built["content"],
                embed=built["embed"],
                components=built["components"],
                files=built.get("files") or None,
                allowed_mentions=disnake.AllowedMentions.none(),
            ) 
        
        return message

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Anunciar_PostarMensagem":
            await message.wait(inter, send=False)
            await inter.edit_original_message(
                components = [
                    disnake.ui.Container(
                        disnake.ui.TextDisplay("-# Selecione o canal para enviar a mensagem"),
                        disnake.ui.ActionRow(
                            disnake.ui.ChannelSelect(
                                custom_id="Anunciar_EnviarMensagem_Canal",
                                placeholder="Selecione o canal",
                                channel_types=[disnake.ChannelType.text],
                                min_values=1,
                                max_values=1,
                            )
                        ),
                        disnake.ui.ActionRow(
                            disnake.ui.Button(
                                label="Enviar a mensagem neste canal",
                                style=disnake.ButtonStyle.blurple,
                                custom_id="Anunciar_EnviarMensagem_EnviarNoCanal",
                                emoji=emoji.arrow,
                            )
                        )
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Voltar",
                            emoji=emoji.back,
                            custom_id="Anunciar_PainelInicial",
                        )
                    )
                ],
            )
    
        elif inter.component.custom_id == "Anunciar_EnviarMensagem_EnviarNoCanal":
            await message.wait(inter, send=False)
            channel: disnake.TextChannel = inter.channel
            msg = await Enviar.send_to_channel(channel)
            await inter.edit_original_message(components=Anunciar.create_buttons())
            await message.success(inter, f"Mensagem enviada com sucesso no canal {channel.mention} (`{msg.id}`)", followup=True, component=[
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Ir para a mensagem",
                        url=msg.jump_url,
                    )
                )
            ])

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Anunciar_EnviarMensagem_Canal":
            await message.wait(inter, send=False)
            # ChannelSelect returns the selected channel ID as a string in values[0]
            selected = inter.values[0]
            channel: disnake.TextChannel | None = None
            if isinstance(selected, str):
                try:
                    channel_id = int(selected)
                    channel = inter.guild.get_channel(channel_id) or self.bot.get_channel(channel_id)
                except Exception:
                    channel = None
            else:
                channel = selected  # Fallback if a channel object is returned

            if channel is None or not hasattr(channel, "send"):
                await message.error(inter, "Não consegui acessar o canal selecionado. Tente novamente ou verifique permissões.", followup=True)
                return

            msg = await Enviar.send_to_channel(channel)
            await inter.edit_original_message(components=Anunciar.create_buttons())
            await message.success(inter, f"Mensagem enviada com sucesso no canal {channel.mention} (`{msg.id}`)", followup=True, component=[
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Ir para a mensagem",
                        url=msg.jump_url,
                    )
                )
            ])

def setup(bot: commands.Bot):
    bot.add_cog(Enviar(bot))
