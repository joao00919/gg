from __future__ import annotations

import os
from typing import Any

from functions.database import database as db

CAPABILITIES = (
    "products",
    "stock",
    "payments",
    "withdrawals",
    "tickets",
    "refunds",
)

ROLE_LABELS = {
    "owner": "Owner",
    "admin": "Admin",
    "finance": "Financeiro",
    "support": "Suporte",
}

DEFAULT_MATRIX = {
    "owner": {cap: True for cap in CAPABILITIES},
    "admin": {
        "products": True,
        "stock": True,
        "payments": True,
        "withdrawals": False,
        "tickets": True,
        "refunds": True,
    },
    "finance": {
        "products": False,
        "stock": False,
        "payments": True,
        "withdrawals": True,
        "tickets": False,
        "refunds": True,
    },
    "support": {
        "products": False,
        "stock": False,
        "payments": False,
        "withdrawals": False,
        "tickets": True,
        "refunds": False,
    },
}

DEFAULT_CONFIG = {
    "enabled": True,
    "role_ids": {
        "admin": None,
        "finance": None,
        "support": None,
    },
    "matrix": DEFAULT_MATRIX,
}


def _split_ids(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value).replace(";", ",").split(",")
    return {str(v).strip() for v in values if str(v).strip().isdigit()}


def _configured_owner_ids() -> set[str]:
    config = db.obter("config.json") or {}
    bot_cfg = config.get("bot") or {}
    ids = set()
    for env_name in ("BOT_OWNER_IDS", "OWNER_IDS", "BOT_OWNER_ID"):
        ids.update(_split_ids(os.getenv(env_name)))
    ids.update(_split_ids(bot_cfg.get("owner")))
    return ids


def get_config() -> dict:
    stored = db.get_document("permission_matrix") or {}
    cfg = {
        "enabled": stored.get("enabled", DEFAULT_CONFIG["enabled"]),
        "role_ids": {**DEFAULT_CONFIG["role_ids"], **(stored.get("role_ids") or {})},
        "matrix": {},
    }
    stored_matrix = stored.get("matrix") or {}
    for role_key, defaults in DEFAULT_MATRIX.items():
        cfg["matrix"][role_key] = {**defaults, **(stored_matrix.get(role_key) or {})}

    # Compatibilidade com os cargos já existentes no bot.
    cargos = db.get_document("cargos") or {}
    cfg["role_ids"]["admin"] = cfg["role_ids"].get("admin") or cargos.get("cargo_admin")
    cfg["role_ids"]["finance"] = cfg["role_ids"].get("finance") or cargos.get("cargo_financeiro")
    cfg["role_ids"]["support"] = cfg["role_ids"].get("support") or cargos.get("cargo_suporte")
    return cfg


def save_config(config: dict) -> None:
    normalized = get_config()
    normalized["enabled"] = bool(config.get("enabled", normalized["enabled"]))
    normalized["role_ids"].update(config.get("role_ids") or {})
    for role_key, values in (config.get("matrix") or {}).items():
        if role_key in normalized["matrix"]:
            for capability, allowed in (values or {}).items():
                if capability in CAPABILITIES:
                    normalized["matrix"][role_key][capability] = bool(allowed)
    db.save_document("permission_matrix", normalized)


def _resolve(subject: Any) -> tuple[str, Any | None, Any | None]:
    guild = getattr(subject, "guild", None)
    member = getattr(subject, "user", None) or getattr(subject, "author", None)
    if member is None and hasattr(subject, "id"):
        member = subject
    user_id = getattr(member, "id", None)
    if user_id is None and isinstance(subject, (int, str)):
        user_id = subject
    if guild is None and member is not None:
        guild = getattr(member, "guild", None)
    return str(user_id or ""), member, guild


def get_role_group(subject: Any) -> str | None:
    user_id, member, guild = _resolve(subject)
    if not user_id:
        return None

    if user_id in _configured_owner_ids():
        return "owner"
    if guild is not None and str(getattr(guild, "owner_id", "")) == user_id:
        return "owner"

    cfg = get_config()
    role_ids = cfg.get("role_ids") or {}
    member_roles = {str(getattr(role, "id", "")) for role in (getattr(member, "roles", None) or [])}

    if str(role_ids.get("admin") or "") in member_roles:
        return "admin"
    if str(role_ids.get("finance") or "") in member_roles:
        return "finance"
    if str(role_ids.get("support") or "") in member_roles:
        return "support"

    # Administrador do Discord funciona como Admin, mas não como Owner.
    guild_permissions = getattr(member, "guild_permissions", None)
    if guild_permissions is not None and bool(getattr(guild_permissions, "administrator", False)):
        return "admin"
    return None


def has_any_access(subject: Any) -> bool:
    return get_role_group(subject) is not None


def has_capability(subject: Any, capability: str) -> bool:
    if capability not in CAPABILITIES:
        return False
    role_group = get_role_group(subject)
    if role_group is None:
        return False
    cfg = get_config()
    if not cfg.get("enabled", True):
        return role_group in {"owner", "admin"}
    return bool((cfg.get("matrix") or {}).get(role_group, {}).get(capability, False))


def matrix_markdown() -> str:
    cfg = get_config()
    headers = ["Função", "Owner", "Admin", "Financeiro", "Suporte"]
    labels = {
        "products": "Produtos",
        "stock": "Estoque",
        "payments": "Pagamentos",
        "withdrawals": "Saques",
        "tickets": "Tickets",
        "refunds": "Reembolsos",
    }
    lines = [" | ".join(headers), " | ".join(["---"] * len(headers))]
    for capability in CAPABILITIES:
        values = [labels[capability]]
        for role_key in ("owner", "admin", "finance", "support"):
            values.append("✓" if cfg["matrix"][role_key].get(capability) else "—")
        lines.append(" | ".join(values))
    return "\n".join(lines)
