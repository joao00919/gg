from disnake.ext import commands
from .cog import ReferralSystem


def setup(bot: commands.Bot):
    bot.add_cog(ReferralSystem(bot))
