from .cog import BusinessRulesConfigCog


def setup(bot):
    bot.add_cog(BusinessRulesConfigCog(bot))


__all__ = ["setup", "BusinessRulesConfigCog"]
