import disnake
from disnake.ext import commands
from Functions.Emoji import Emoji

class RepostagemCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def Painel() -> list[disnake.ui.Container]:
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"""
# {Emoji.sync}
-# Painel > Automações > **Repostagem**
                """),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay("""
Configure a repostagem de mensagens do servidor.
Em breve mais funcionalidades!
                """),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=Emoji.back, custom_id="VoltarAutomações"),
            )
        ]



def setup(bot: commands.Bot):
    bot.add_cog(RepostagemCommand(bot))
