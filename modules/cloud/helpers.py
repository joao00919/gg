import disnake

from functions.database import database as db
from functions.emoji import emoji
from .local_verification import count_locally_verified, get_verification_mode


async def get_status_text(inter: disnake.Interaction):
    cloud_config = db.get_document("cloud_data") or {}
    cargos_config = db.get_document("cargos") or {}
    verified_role_id = cargos_config.get("cargo_verificado")
    mode = get_verification_mode()

    log_channel_id = cloud_config.get("log_channel_id")
    logs_channel = f"<#{log_channel_id}>" if log_channel_id else "`Não definido`"
    verified_role_mention = f"<@&{verified_role_id}>" if verified_role_id else "`Não definido`"

    verified_members = count_locally_verified(inter.guild) if inter.guild else 0
    oauth_ready = bool(cloud_config.get("client_id"))
    local_ready = bool(verified_role_id)
    is_ready = oauth_ready if mode == "oauth" else local_ready

    if mode == "oauth" and oauth_ready:
        try:
            from .update_api import get_websocket_manager

            ws_manager = get_websocket_manager()
            if ws_manager.is_connected():
                response = await ws_manager.check_auth_count(cloud_config["client_id"])
                if response.get("success"):
                    verified_members = int(response.get("data", {}).get("count", verified_members))
        except Exception as exc:
            print(f"[ZYNEX Cloud] Erro ao obter contagem OAuth: {exc}")

    status_emoji = emoji.on if is_ready else emoji.off
    status_label = "`Pronto para verificar`" if is_ready else "`Configuração pendente`"
    mode_label = "OAuth2 externo" if mode == "oauth" else "Verificação local por cargo"

    # Não use atributos inexistentes como valor padrão de getattr: o Python
    # avalia o argumento padrão antes da chamada e isso travava o painel.
    members_emoji = (
        getattr(emoji, "members", None)
        or getattr(emoji, "user", None)
        or "👥"
    )
    role_emoji = (
        getattr(emoji, "role", None)
        or getattr(emoji, "shield", None)
        or "🛡️"
    )

    return (
        f"{status_emoji} **Status:** {status_label}\n"
        f"{emoji.shield} **Modo:** `{mode_label}`\n"
        f"{members_emoji} **Membros Verificados:** `{verified_members}`\n"
        f"{emoji.textc} **Canal de Logs:** {logs_channel}\n"
        f"{role_emoji} **Cargo de Verificado:** {verified_role_mention}"
    )


class LogChannelModal(disnake.ui.Modal):
    def __init__(self, bot, current_channel_id: str = ""):
        self.bot = bot
        components = [
            disnake.ui.Label(
                text="Selecione o Canal de Logs",
                component=disnake.ui.ChannelSelect(
                    placeholder="Escolha um canal de texto",
                    custom_id="log_channel_select",
                    channel_types=[disnake.ChannelType.text],
                    min_values=1,
                    max_values=1,
                ),
                description="O SyncCloud usará este canal para enviar os logs de verificação.",
            ),
        ]
        super().__init__(title="Definir Canal de Logs", components=components, custom_id="log_channel_modal")

    async def callback(self, inter: disnake.ModalInteraction):
        try:
            valores = inter.resolved_values
            selected = valores.get("log_channel_select")
            # Normalize selection to a string channel ID
            if isinstance(selected, (list, tuple)):
                selected = selected[0] if selected else None
            if isinstance(selected, (str, int)):
                log_channel_id = str(selected)
            elif hasattr(selected, "id"):
                # Likely a channel object
                try:
                    log_channel_id = str(int(selected.id))
                except Exception:
                    log_channel_id = None
            else:
                log_channel_id = None

            cloud_cog = self.bot.get_cog("Cloud")
            if cloud_cog:
                await cloud_cog.process_log_channel(inter, log_channel_id)
            else:
                if not inter.response.is_done():
                    await inter.response.send_message("Erro: Mensagem não encontrada", ephemeral=True)
        except Exception as e:
            if not inter.response.is_done():
                await inter.response.send_message(f"Erro ao processar modal: {str(e)}", ephemeral=True)


