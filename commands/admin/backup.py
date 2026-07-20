import disnake
from disnake.ext import commands

from functions.message import message
from functions.perms import perms
from functions.database import database
from functions.server_check import exclude_from_check

class BackupCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(
        name="backup",
        description="Gerencie os backups do servidor.",
    )
    @exclude_from_check
    async def backup(self, inter: disnake.ApplicationCommandInteraction):
        if not await perms.check_owner(inter):
            return await message.missing_perms(inter)
        
        backup_cog = self.bot.get_cog("Backup")
        if backup_cog:
            await backup_cog.display_backup_panel(inter)
        else:
            await message.error(inter, "O módulo de backup não está carregado.", send=True)

def setup(bot: commands.Bot):
    bot.add_cog(BackupCommand(bot))
