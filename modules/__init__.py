from .automations import setup as automations_setup
from .customization import setup as customization_setup
from .loja import setup as loja_setup
from .protection import setup as protection_setup
from .settings import setup as settings_setup
from .tickets import setup as tickets_setup
from .giveaways import setup as giveaways_setup
from .cloud import setup as cloud_setup
from functions.plan import should_load_module
from .rendimentos import setup as rendimentos_setup
from .manager_integration import setup as manager_integration_setup

def setup(bot):
    manager_integration_setup(bot)
    # Carrega módulos baseado no plano configurado
    if should_load_module("automations"):
        automations_setup(bot)
    if should_load_module("customization"):
        customization_setup(bot)
    if should_load_module("loja"):
        loja_setup(bot)
    if should_load_module("rendimentos"):
        rendimentos_setup(bot)
    if should_load_module("protection"):
        protection_setup(bot)
    if should_load_module("settings"):
        settings_setup(bot)
    if should_load_module("tickets"):
        tickets_setup(bot)
    if should_load_module("giveaways"):
        giveaways_setup(bot)
    if should_load_module("cloud"):
        cloud_setup(bot)

__all__ = ["setup"]