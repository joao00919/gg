"""Proteções de compatibilidade para interações do Discord/Disnake.

O Discord rejeita select menus opcionais dentro de modais quando o componente é
serializado com ``min_values=0`` e ``required=true``. Algumas versões do
Disnake mantêm ``required=True`` como padrão mesmo quando ``min_values`` foi
explicitamente definido como zero. Este módulo normaliza o payload no último
momento, sem alterar IDs, labels, opções ou callbacks.

Também instala um ``on_error`` no bot para que exceções de listeners de botão,
select e modal sejam registradas e respondidas ao usuário, em vez de apenas
aparecerem como ``Ignoring exception in on_button_click`` no console.
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Callable

import disnake

from functions.interaction_runtime import respond_error

logger = logging.getLogger("zynex.discord_runtime")

_SELECT_COMPONENT_TYPES = {
    3,  # String select
    5,  # User select
    6,  # Role select
    7,  # Mentionable select
    8,  # Channel select
}
_PATCH_MARKER = "_zynex_optional_select_patch"


def _normalize_optional_modal_selects(value: Any) -> int:
    """Normaliza recursivamente selects opcionais e retorna quantos corrigiu."""
    changed = 0
    if isinstance(value, dict):
        component_type = value.get("type")
        min_values = value.get("min_values")
        if (
            component_type in _SELECT_COMPONENT_TYPES
            and min_values == 0
            and value.get("required") is not False
        ):
            value["required"] = False
            changed += 1
        for child in value.values():
            changed += _normalize_optional_modal_selects(child)
    elif isinstance(value, list):
        for child in value:
            changed += _normalize_optional_modal_selects(child)
    return changed


def install_modal_payload_safety() -> bool:
    """Instala uma correção idempotente em ``disnake.ui.Modal.to_components``."""
    modal_cls = disnake.ui.Modal
    current: Callable[..., Any] = modal_cls.to_components
    if getattr(current, _PATCH_MARKER, False):
        return False

    original = current

    def safe_to_components(self: disnake.ui.Modal):
        payload = original(self)
        changed = _normalize_optional_modal_selects(payload)
        if changed:
            logger.debug(
                "Modal normalizado | custom_id=%s | selects opcionais=%s",
                getattr(self, "custom_id", "?"),
                changed,
            )
        return payload

    setattr(safe_to_components, _PATCH_MARKER, True)
    setattr(safe_to_components, "_zynex_original", original)
    modal_cls.to_components = safe_to_components  # type: ignore[method-assign]
    logger.info("Proteção global para selects opcionais em modais ativada.")
    return True


def _find_interaction(args: tuple[Any, ...], kwargs: dict[str, Any]) -> disnake.Interaction | None:
    for value in (*args, *kwargs.values()):
        if isinstance(value, disnake.Interaction):
            return value
    return None


def install_listener_error_fallback(bot: Any) -> None:
    """Responde erros não tratados de listeners de componentes.

    O ``Client._run_event`` chama ``bot.on_error`` para exceções levantadas em
    listeners como ``on_button_click``. Sobrescrever esse método é a forma
    suportada de impedir que a interação expire silenciosamente.
    """
    if getattr(bot, "_zynex_listener_error_fallback", False):
        return

    async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
        exc_type, exc, tb = sys.exc_info()
        logger.error(
            "Erro não tratado em listener | evento=%s | erro=%s: %s",
            event_method,
            getattr(exc_type, "__name__", "Exception"),
            exc,
            exc_info=(exc_type, exc, tb) if exc_type and exc else None,
        )
        inter = _find_interaction(args, kwargs)
        if inter is None:
            return
        try:
            await respond_error(
                inter,
                "A ação não pôde ser concluída. O erro foi registrado no console do bot.",
            )
        except Exception:
            logger.exception("Falha ao responder o erro não tratado ao usuário")

    bot.on_error = on_error
    bot._zynex_listener_error_fallback = True
    logger.info("Fallback global de erros em botões, selects e modais ativado.")


def install_discord_runtime_safety(bot: Any | None = None) -> None:
    """Instala todas as proteções disponíveis."""
    install_modal_payload_safety()
    if bot is not None:
        install_listener_error_fallback(bot)
