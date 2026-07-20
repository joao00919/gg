from disnake.ext import commands

def setup(bot: commands.Bot):
    """Extensões opcionais desativadas nesta edição segura."""
    return None

__all__ = ["setup"]
