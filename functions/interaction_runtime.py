"""Entrega robusta de painéis e respostas de interação.

Evita dois problemas comuns no Discord:
1. a interação expirar sem resposta;
2. um emoji personalizado inválido impedir o envio de todo o painel.

O primeiro envio sempre preserva os emojis personalizados. Caso o Discord rejeite
algum ID de emoji, o mesmo painel é reenviado com equivalentes Unicode, sem perder
botões, selects ou funções.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

import disnake

logger = logging.getLogger("zynex.interactions")

_UNICODE_BY_NAME = {
    "zenyx2": "✨",
    "cart": "🛒",
    "ticket": "🎫",
    "cloud": "☁️",
    "chart": "📊",
    "wand": "🪄",
    "thunder": "⚡",
    "shield": "🛡️",
    "giveaway": "🎉",
    "settings": "⚙️",
    "settings2": "⚙️",
    "config": "⚙️",
    "edit": "✏️",
    "delete": "🗑️",
    "back": "↩️",
    "reload": "🔄",
    "correct": "✅",
    "wrong": "❌",
    "warn": "⚠️",
    "information": "ℹ️",
    "cardbox": "📦",
    "wallet": "👛",
    "bank": "🏦",
    "pix": "💠",
    "coupon": "🎟️",
    "plus": "➕",
    "search": "🔎",
    "role": "👥",
    "member": "👤",
    "members": "👥",
    "textc": "📋",
    "termos": "📋",
    "image": "🖼️",
    "colors": "🎨",
    "flag": "🚩",
    "on": "🟢",
    "off": "⚫",
    "online": "🟢",
    "loading": "🔄",
    "truck": "🚚",
    "save": "💾",
    "play": "▶️",
    "pause": "⏸️",
    "lock": "🔒",
    "unlock": "🔓",
    "voice": "🔊",
    "voice_lock": "🔐",
    "web": "🌐",
    "website": "🌐",
    "rocket": "🚀",
    "trophy": "🏆",
    "star": "⭐",
    "sparkles": "✨",
    "speech": "💬",
    "sound": "🔊",
    "clock": "🕒",
    "time": "⏱️",
    "calendar": "📅",
    "dollar": "💵",
    "coin": "🪙",
    "card": "💳",
    "folder": "📁",
    "gift": "🎁",
    "fire": "🔥",
    "robot": "🤖",
    "receipt": "📄",
    "embed": "🧾",
    "message": "💬",
    "hammer": "🔨",
    "arrow": "➡️",
    "minus": "➖",
    "interrogation": "❓",
    "double_check": "✅",
    "group": "👥",
    "verified": "✅",
    "members": "👥",
    "route": "🧭",
}


def _emoji_name(value: Any) -> str:
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if name:
        return str(name)
    raw = str(value)
    if raw.startswith("<") and raw.count(":") >= 2:
        return raw.split(":", 2)[1]
    return raw


def _is_custom_emoji(value: Any) -> bool:
    if value is None:
        return False
    if getattr(value, "id", None):
        return True
    raw = str(value)
    return raw.startswith("<:") or raw.startswith("<a:")


def _unicode_fallback(value: Any) -> str | None:
    name = _emoji_name(value)
    return _UNICODE_BY_NAME.get(name)


def _sanitize_item(item: Any) -> None:
    """Substitui somente emojis customizados; preserva toda a estrutura do painel."""
    if item is None:
        return

    if hasattr(item, "emoji"):
        try:
            current = getattr(item, "emoji", None)
            if _is_custom_emoji(current):
                setattr(item, "emoji", _unicode_fallback(current))
        except Exception:
            pass

    options = getattr(item, "options", None)
    if options:
        for option in options:
            try:
                current = getattr(option, "emoji", None)
                if _is_custom_emoji(current):
                    option.emoji = _unicode_fallback(current)
            except Exception:
                pass

    children = getattr(item, "children", None)
    if children:
        for child in children:
            _sanitize_item(child)

    component = getattr(item, "component", None)
    if component is not None:
        _sanitize_item(component)


def with_safe_emojis(panel: dict[str, Any]) -> dict[str, Any]:
    """Cria uma cópia do painel com fallback Unicode para emojis customizados."""
    safe = copy.deepcopy(panel)
    components = safe.get("components")
    if components is None:
        return safe
    if not isinstance(components, (list, tuple)):
        components = [components]
        safe["components"] = components
    for item in components:
        _sanitize_item(item)
    return safe


def _is_components_v2_panel(panel: dict[str, Any]) -> bool:
    return bool(panel.get("components")) and not panel.get("embed") and not panel.get("embeds") and panel.get("content") is None


def _send_kwargs(panel: dict[str, Any], *, initial: bool) -> dict[str, Any]:
    kwargs = dict(panel)
    if initial and _is_components_v2_panel(kwargs):
        kwargs.setdefault("flags", disnake.MessageFlags(is_components_v2=True))
    return kwargs


async def _send_new(inter: disnake.Interaction, panel: dict[str, Any], *, ephemeral: bool) -> Any:
    if not inter.response.is_done():
        return await inter.response.send_message(
            ephemeral=ephemeral, **_send_kwargs(panel, initial=True)
        )
    # Uma interação pode ter sido reconhecida por outro handler/erro entre as
    # tentativas. Nesse caso, usa follow-up em vez de expirar silenciosamente.
    return await inter.followup.send(
        ephemeral=ephemeral, wait=True, **_send_kwargs(panel, initial=True)
    )


async def _edit_existing(inter: disnake.Interaction, panel: dict[str, Any]) -> Any:
    kwargs = dict(panel)
    # Mensagens Components V2 não aceitam conteúdo/embed simultaneamente.
    if _is_components_v2_panel(kwargs):
        kwargs.pop("content", None)
        kwargs.pop("embed", None)
        kwargs.pop("embeds", None)

    # Em cliques de botão/select, editar pela resposta inicial reconhece a
    # interação imediatamente e evita o aviso "o aplicativo não respondeu".
    if not inter.response.is_done():
        response_editor = getattr(inter.response, "edit_message", None)
        if response_editor is not None:
            return await response_editor(**kwargs)

    editor = getattr(inter, "edit_original_response", None) or getattr(inter, "edit_original_message")
    return await editor(**kwargs)


async def respond_panel(
    inter: disnake.Interaction,
    panel: dict[str, Any],
    *,
    ephemeral: bool = True,
    prefer_edit: bool = False,
) -> Any:
    """Envia ou edita um painel com retentativa automática sem IDs inválidos."""
    response_done = bool(inter.response.is_done())
    should_edit = prefer_edit or response_done

    async def execute(payload: dict[str, Any]) -> Any:
        # Reavalia o estado em cada tentativa. Isso cobre respostas reconhecidas
        # entre uma falha HTTP e a retentativa.
        if prefer_edit or inter.response.is_done():
            try:
                return await _edit_existing(inter, payload)
            except disnake.NotFound:
                # Não existe mensagem original editável; cria um follow-up.
                return await inter.followup.send(
                    ephemeral=ephemeral, wait=True, **_send_kwargs(payload, initial=True)
                )
        return await _send_new(inter, payload, ephemeral=ephemeral)

    try:
        return await execute(panel)
    except (disnake.HTTPException, ValueError, TypeError) as first_error:
        logger.warning(
            "Discord rejeitou o painel; repetindo com emojis seguros | status=%s | erro=%s",
            getattr(first_error, "status", "?"),
            str(first_error)[:300],
        )
        safe_panel = with_safe_emojis(panel)
        try:
            return await execute(safe_panel)
        except Exception:
            logger.exception("Falha ao enviar o painel mesmo após aplicar fallback de emojis")
            raise


async def respond_error(inter: disnake.Interaction, text: str, *, ephemeral: bool = True) -> None:
    """Garante que o usuário receba uma resposta mesmo após uma exceção."""
    message = f"❌ {text}"
    try:
        if not inter.response.is_done():
            await inter.response.send_message(message, ephemeral=ephemeral)
            return
    except Exception:
        logger.exception("Falha ao responder erro pela resposta inicial")

    # Quando já existe uma mensagem de "Carregando...", substitui essa mensagem
    # pelo erro em vez de deixá-la presa para sempre.
    try:
        editor = getattr(inter, "edit_original_response", None) or getattr(
            inter, "edit_original_message", None
        )
        if editor is not None:
            await editor(
                components=[
                    disnake.ui.Container(
                        disnake.ui.TextDisplay(message),
                        accent_colour=disnake.Colour.red(),
                    )
                ]
            )
            return
    except Exception:
        logger.debug("Não foi possível substituir a resposta original pelo erro", exc_info=True)

    try:
        await inter.followup.send(message, ephemeral=ephemeral)
    except Exception:
        logger.exception("Falha ao responder erro por follow-up")
