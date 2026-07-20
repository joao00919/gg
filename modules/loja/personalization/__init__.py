"""
Módulo de personalização da loja
"""

def setup(bot):
    from .cog import PersonalizarLoja
    from .mensagens.cog import PersonalizarMensagens
    
    bot.add_cog(PersonalizarLoja(bot))
    bot.add_cog(PersonalizarMensagens(bot))