from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

from functions.database import database as db


def _split_ids(value: Any) -> set[str]:
    """Normaliza IDs vindos do .env ou do config legado."""
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        values: Iterable[Any] = value
    else:
        text = str(value).strip()
        if not text:
            return set()
        values = text.replace(";", ",").split(",")
    return {str(item).strip() for item in values if str(item).strip().isdigit()}


def _env_ids(*names: str) -> set[str]:
    result: set[str] = set()
    for name in names:
        result.update(_split_ids(os.getenv(name)))
    return result


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _resolve_subject(subject: Any) -> tuple[str, Any | None, Any | None]:
    """Retorna (user_id, membro, guild) a partir de ID, Member ou Interaction."""
    if subject is None:
        return "", None, None

    guild = getattr(subject, "guild", None)
    member = getattr(subject, "user", None) or getattr(subject, "author", None)
    if member is None and hasattr(subject, "id"):
        member = subject

    user_id = getattr(member, "id", None)
    if user_id is None and isinstance(subject, (str, int)):
        user_id = subject

    if guild is None and member is not None:
        guild = getattr(member, "guild", None)

    return str(user_id or ""), member, guild


class perms:
    """Controle centralizado de acesso administrativo.

    Ordem de autorização:
    1. BOT_OWNER_IDS / OWNER_IDS no .env;
    2. BOT_ADMIN_IDS / ADMIN_USER_IDS no .env;
    3. owner/perms do config legado;
    4. dono do servidor Discord;
    5. membros com Administrador, quando ALLOW_GUILD_ADMIN=true.
    """

    @staticmethod
    def _configured_ids() -> tuple[set[str], set[str]]:
        config = db.obter("config.json") or {}
        bot_config = config.get("bot") or {}

        owners = _env_ids("BOT_OWNER_IDS", "OWNER_IDS", "BOT_OWNER_ID")
        owners.update(_split_ids(bot_config.get("owner")))

        admins = _env_ids("BOT_ADMIN_IDS", "ADMIN_USER_IDS", "ADMIN_IDS")
        admins.update(_split_ids(bot_config.get("perms")))
        return owners, admins

    @staticmethod
    async def check(subject: Any) -> bool:
        user_id, member, guild = _resolve_subject(subject)
        if not user_id:
            return False

        owners, admins = perms._configured_ids()
        if user_id in owners or user_id in admins:
            return True

        if guild is not None and str(getattr(guild, "owner_id", "")) == user_id:
            return True

        if _truthy("ALLOW_GUILD_ADMIN", default=True) and member is not None:
            guild_permissions = getattr(member, "guild_permissions", None)
            if guild_permissions is not None and bool(getattr(guild_permissions, "administrator", False)):
                return True

        # Usuários com função na matriz podem abrir o /botconfig; cada ação
        # crítica continua validada pela capacidade específica no backend.
        try:
            from functions.permission_matrix import has_any_access
            if has_any_access(subject):
                return True
        except Exception:
            pass

        return False

    @staticmethod
    async def check_owner(subject: Any) -> bool:
        user_id, _member, guild = _resolve_subject(subject)
        if not user_id:
            return False

        owners, _admins = perms._configured_ids()
        if user_id in owners:
            return True

        return guild is not None and str(getattr(guild, "owner_id", "")) == user_id

    @staticmethod
    async def check_bot_owner(subject: Any) -> bool:
        """Valida somente o proprietário configurado do bot, sem herdar dono do servidor."""
        user_id, _member, _guild = _resolve_subject(subject)
        if not user_id:
            return False
        owners, _admins = perms._configured_ids()
        return user_id in owners
