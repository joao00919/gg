"""Verificação obrigatória de membros no ZYNEX Cloud."""
from __future__ import annotations

from urllib.parse import urlencode

import disnake

from functions.database import database as db
from functions.emoji import emoji
from .local_verification import get_verification_mode, is_locally_verified


def _oauth_url(inter: disnake.Interaction) -> str | None:
    cloud = db.get_document("cloud_data") or {}
    client_id = str(cloud.get("client_id") or "").strip()
    if not client_id:
        return None
    from .cloud_config import get_auth_callback_url

    redirect_uri = get_auth_callback_url()
    if not redirect_uri:
        return None
    state = f"{client_id}-{inter.guild.id if inter.guild else 0}"
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify email guilds.join",
            "state": state,
        }
    )
    return f"https://discord.com/api/oauth2/authorize?{query}"


async def is_user_verified(member: disnake.Member) -> bool:
    try:
        if is_locally_verified(member):
            return True
        cloud = db.get_document("cloud_data") or {}
        if get_verification_mode() != "oauth" or not cloud.get("client_id"):
            return False
        from .update_api import get_websocket_manager

        manager = get_websocket_manager()
        if not manager.is_connected():
            return False
        response = await manager.check_user_verification(cloud.get("client_id"), member.id)
        return bool(response.get("success") and response.get("data", {}).get("is_verified"))
    except Exception as exc:
        print(f"[ZYNEX Cloud] Erro ao consultar verificação: {exc}")
        return False


def is_verification_required() -> bool:
    try:
        cloud = db.get_document("cloud_data") or {}
        definitions = cloud.get("definitions", {}) or {}
        enabled = bool((definitions.get("require_oauth2") or {}).get("enabled", False))
        if not enabled:
            return False
        if get_verification_mode() == "oauth":
            return bool(cloud.get("client_id"))
        cargos = db.get_document("cargos") or {}
        return bool(cargos.get("cargo_verificado"))
    except Exception:
        return False


def get_verification_message_and_view(
    inter: disnake.Interaction,
) -> tuple[str, disnake.ui.View] | tuple[None, None]:
    try:
        view = disnake.ui.View(timeout=None)
        if get_verification_mode() == "oauth":
            url = _oauth_url(inter)
            if not url:
                return None, None
            view.add_item(
                disnake.ui.Button(
                    label="Verificar com Discord",
                    emoji=emoji.verified,
                    style=disnake.ButtonStyle.link,
                    url=url,
                )
            )
        else:
            view.add_item(
                disnake.ui.Button(
                    label="Verificar agora",
                    emoji=emoji.verified,
                    style=disnake.ButtonStyle.success,
                    custom_id="Cloud_GetAuthLink",
                )
            )
        return (
            "Este servidor exige verificação. Clique no botão abaixo para liberar seu acesso.",
            view,
        )
    except Exception as exc:
        print(f"[ZYNEX Cloud] Erro ao montar mensagem de verificação: {exc}")
        return None, None


async def send_verification_required_message(inter: disnake.Interaction) -> bool:
    try:
        if not is_verification_required():
            return False
        member = inter.user if isinstance(inter.user, disnake.Member) else None
        if member is None and inter.guild:
            member = inter.guild.get_member(inter.user.id)
        if member is None or await is_user_verified(member):
            return False
        message_text, view = get_verification_message_and_view(inter)
        if not message_text or view is None:
            return False
        kwargs = {"content": message_text, "view": view, "ephemeral": True}
        if inter.response.is_done():
            await inter.followup.send(**kwargs)
        else:
            await inter.response.send_message(**kwargs)
        return True
    except Exception as exc:
        print(f"[ZYNEX Cloud] Erro ao enviar verificação obrigatória: {exc}")
        return False
