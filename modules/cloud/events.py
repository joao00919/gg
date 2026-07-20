import disnake
from disnake.ext import commands
import logging
from functions.database import database as db
from modules.cloud.update_api import get_websocket_manager

logger = logging.getLogger(__name__)

class CloudEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_member_join")
    async def on_member_join_persistent_auth(self, member: disnake.Member):
        try:
            cloud_config = db.get_document("cloud_data") or {}
            definitions = cloud_config.get("definitions", {}) or {}
            if not bool((definitions.get("persistent_oauth2") or {}).get("enabled", False)):
                return

            from .local_verification import get_verification_mode, get_verified_role, is_locally_verified

            if get_verification_mode() == "local":
                role = get_verified_role(member.guild)
                if role and is_locally_verified(member) and role not in member.roles:
                    await member.add_roles(role, reason="Verificação persistente ZYNEX Cloud")
                return

            client_id = cloud_config.get("client_id")
            if not client_id:
                return
            ws_manager = get_websocket_manager()
            if not ws_manager.is_connected():
                return
            response = await ws_manager.check_user_verification(client_id, member.id)
            if response.get("success") and response.get("data", {}).get("is_verified"):
                role = get_verified_role(member.guild)
                if role and role not in member.roles:
                    await member.add_roles(role, reason="Verificação persistente ZYNEX Cloud")
        except Exception as exc:
            logger.error(f"[ZYNEX Cloud] Erro ao restaurar verificação: {exc}")

def setup(bot: commands.Bot):
    bot.add_cog(CloudEvents(bot))
