from disnake.ext import commands
from . import cupom_em_massa, entregar, perfil, ranking, sincronizar_clientes

def setup(bot: commands.Bot):
    """Carrega todos os comandos de vendas"""
    cupom_em_massa.setup(bot)
    entregar.setup(bot)
    perfil.setup(bot)
    ranking.setup(bot)
    sincronizar_clientes.setup(bot)
