from disnake.ext import commands
from .cog import Cloud
from .events import CloudEvents


def setup(bot: commands.Bot):
    bot.add_cog(Cloud(bot))
    bot.add_cog(CloudEvents(bot))


__all__ = ["setup"]
