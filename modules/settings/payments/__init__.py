from .cog import setup as setup_payments
from .wallet_panel import setup as setup_wallet_panel


def setup(bot):
    """Setup all payment-related cogs"""
    setup_payments(bot)
    setup_wallet_panel(bot)


__all__ = ["setup"]
