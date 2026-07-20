from disnake.ext import commands
from functions.plan import should_load_module

def setup(bot: commands.Bot):
    bot.load_extension("tasks.zynex_operations")
    # Carrega tasks baseado no plano configurado
    if should_load_module("automations"):
        bot.load_extension("tasks.automations.cog")
    # O painel de proteção referencia Backup e Restauração; mantenha o módulo carregado.
    bot.load_extension("tasks.backup")
    if should_load_module("protection"):
        bot.load_extension("tasks.protection")
    if should_load_module("bot"):
        bot.load_extension("tasks.bot.cog")
        bot.load_extension("tasks.bot.autorole")
    if should_load_module("giveaways"):
        bot.load_extension("tasks.giveaways.cog")
    
    # Nubank IMAP Monitor (sempre ativo se configurado)
    #bot.load_extension("tasks.payments.nubank_monitor")
    