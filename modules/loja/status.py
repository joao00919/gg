"""Estado operacional global da loja.

Este módulo centraliza o botão Ligar/Desligar Vendas para que o painel e o
checkout consultem a mesma configuração persistida.
"""
from __future__ import annotations

from functions.database import database as db

DOC_NAME = "loja_status"


def get_status() -> dict:
    raw = db.get_document(DOC_NAME) or {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "enabled": bool(raw.get("enabled", True)),
        "updated_by": raw.get("updated_by"),
        "updated_at": raw.get("updated_at"),
    }


def sales_enabled() -> bool:
    return bool(get_status()["enabled"])


def set_sales_enabled(enabled: bool, *, updated_by: int | None = None, updated_at: int | None = None) -> dict:
    data = {
        "enabled": bool(enabled),
        "updated_by": str(updated_by) if updated_by is not None else None,
        "updated_at": updated_at,
    }
    db.save_document(DOC_NAME, data)
    return data


def toggle_sales(*, updated_by: int | None = None, updated_at: int | None = None) -> dict:
    return set_sales_enabled(
        not sales_enabled(),
        updated_by=updated_by,
        updated_at=updated_at,
    )
