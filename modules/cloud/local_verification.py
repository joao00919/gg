"""Verificação local do ZYNEX Cloud.

O membro clica no botão da mensagem de verificação e recebe o cargo configurado.
O modo OAuth2 externo continua disponível, mas não é obrigatório para a
verificação local funcionar.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import disnake

from functions.database import database as db


def get_verification_mode() -> str:
    cloud = db.get_document("cloud_data") or {}
    mode = str(cloud.get("verification_mode") or "local").strip().lower()
    return mode if mode in {"local", "oauth"} else "local"


def get_verified_role_id() -> int | None:
    cargos = db.get_document("cargos") or {}
    raw = cargos.get("cargo_verificado")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def get_verified_role(guild: disnake.Guild | None) -> disnake.Role | None:
    if guild is None:
        return None
    role_id = get_verified_role_id()
    return guild.get_role(role_id) if role_id else None


def _records_document() -> dict[str, Any]:
    data = db.get_document("cloud_verified_users") or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("items", {})
    return data


def _record_key(guild_id: int, user_id: int) -> str:
    return f"{int(guild_id)}:{int(user_id)}"


def is_locally_verified(member: disnake.Member) -> bool:
    role = get_verified_role(member.guild)
    if role and role in member.roles:
        return True
    records = _records_document().get("items", {})
    record = records.get(_record_key(member.guild.id, member.id)) or {}
    return bool(record.get("verified", False))


def count_locally_verified(guild: disnake.Guild | None) -> int:
    if guild is None:
        return 0
    role = get_verified_role(guild)
    if role is not None:
        return sum(1 for member in guild.members if role in member.roles)
    prefix = f"{guild.id}:"
    records = _records_document().get("items", {})
    return sum(
        1
        for key, record in records.items()
        if str(key).startswith(prefix) and bool((record or {}).get("verified"))
    )


def save_verified_role(role: disnake.Role) -> None:
    cargos = db.get_document("cargos") or {}
    cargos["cargo_verificado"] = int(role.id)
    db.save_document("cargos", cargos)
    cloud = db.get_document("cloud_data") or {}
    cloud["verification_mode"] = "local"
    definitions = cloud.setdefault("definitions", {})
    definitions.setdefault("require_oauth2", {})["enabled"] = True
    db.save_document("cloud_data", cloud)


def _bot_can_manage_role(guild: disnake.Guild, role: disnake.Role) -> tuple[bool, str | None]:
    me = guild.me
    if me is None:
        return False, "Não foi possível localizar o usuário do bot no servidor."
    if not me.guild_permissions.manage_roles:
        return False, "O bot precisa da permissão `Gerenciar Cargos`."
    if role.is_default() or role.managed:
        return False, "O cargo de verificado não pode ser o @everyone nem um cargo gerenciado."
    if me.top_role <= role:
        return False, "Coloque o cargo do bot acima do cargo de verificado."
    return True, None


async def verify_member(member: disnake.Member, bot) -> tuple[bool, str]:
    role = get_verified_role(member.guild)
    if role is None:
        return False, "O cargo de verificado ainda não foi configurado no ZYNEX Cloud."

    manageable, error = _bot_can_manage_role(member.guild, role)
    if not manageable:
        return False, error or "O bot não consegue gerenciar o cargo de verificado."

    already_verified = role in member.roles
    if not already_verified:
        try:
            await member.add_roles(role, reason="Verificação ZYNEX Cloud")
        except disnake.Forbidden:
            return False, "Não tenho permissão para adicionar o cargo de verificado."
        except disnake.HTTPException as exc:
            return False, f"O Discord recusou a atribuição do cargo: {str(exc)[:180]}"

    # Remover autorole, caso a opção esteja habilitada.
    try:
        cloud = db.get_document("cloud_data") or {}
        remove_auto = bool(
            (cloud.get("definitions", {}).get("remove_autorole") or {}).get("enabled", False)
        )
        if remove_auto:
            auto_id = (db.get_document("cargos") or {}).get("cargo_auto_role")
            auto_role = member.guild.get_role(int(auto_id)) if auto_id else None
            if auto_role and auto_role in member.roles:
                await member.remove_roles(auto_role, reason="Verificação ZYNEX Cloud")
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    records = _records_document()
    records["items"][_record_key(member.guild.id, member.id)] = {
        "verified": True,
        "guild_id": int(member.guild.id),
        "user_id": int(member.id),
        "role_id": int(role.id),
        "verified_at": now.isoformat(),
        "source": "local_button",
    }
    db.save_document("cloud_verified_users", records)

    try:
        from .auth_logs import send_auth_log

        await send_auth_log(
            bot,
            {
                "success": True,
                "user": {
                    "id": str(member.id),
                    "username": member.name,
                    "discriminator": getattr(member, "discriminator", "0"),
                    "email": "Não coletado",
                    "ip": "Não coletado",
                    "verified_at": now.isoformat(),
                },
            },
        )
    except Exception:
        pass

    if already_verified:
        return True, "Você já estava verificado neste servidor."
    return True, "Verificação concluída. Seu acesso foi liberado."
