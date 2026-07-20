from __future__ import annotations

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.message import embed_message
from modules.tickets.purchase_link import mode_requires_purchase, selector_payload
from .open_ticket import TicketFormModal, open_ticket


async def _send_purchase_selector(inter: disnake.Interaction, panel_id: str, panel_data: dict, option_data: dict | None = None) -> None:
    payload = selector_payload(inter.user.id, panel_id, panel_data, str(option_data.get("id")) if option_data else None)
    if inter.response.is_done():
        await inter.followup.send(ephemeral=True, **payload)
    else:
        await inter.response.send_message(ephemeral=True, **payload)


async def _ensure_verified(inter: disnake.Interaction) -> bool:
    """Mantém a verificação OAuth2, sem bloquear o ticket se o módulo estiver indisponível."""
    try:
        from modules.cloud.verification_check import (
            is_user_verified,
            is_verification_required,
            send_verification_required_message,
        )
        if not is_verification_required():
            return True
        member = inter.user if isinstance(inter.user, disnake.Member) else (
            inter.guild.get_member(inter.user.id) if inter.guild else None
        )
        if not member or await is_user_verified(member):
            return True
        await send_verification_required_message(inter)
        return False
    except Exception as exc:
        print(f"[Tickets] Verificação OAuth2 ignorada por erro: {exc}")
        return True


async def _initiate_ticket_creation(
    inter: disnake.Interaction,
    bot: commands.Bot,
    panel_id: str,
    option_data: dict | None = None,
    ticket_context: dict | None = None,
):
    config = db.get_document("tickets_config") or {}
    panel_data = (config.get("panels") or {}).get(panel_id)
    if not panel_data:
        if inter.response.is_done():
            return await embed_message.error(inter, "Painel de ticket não encontrado.", followup=True)
        return await embed_message.error(inter, "Painel de ticket não encontrado.", send=True)

    if not await _ensure_verified(inter):
        return

    questions = None
    if option_data:
        option_id = str(option_data.get("id"))
        questions = (panel_data.get("forms") or {}).get(option_id, [])

    if questions:
        if inter.response.is_done():
            # Este caso só ocorre em fluxos antigos. O fluxo novo de compra abre o modal
            # diretamente pela interação do seletor.
            return await inter.followup.send(
                f"{emoji.interrogation} Clique novamente no painel para abrir o formulário.",
                ephemeral=True,
            )
        return await inter.response.send_modal(
            TicketFormModal(
                inter,
                bot,
                panel_data,
                panel_id,
                questions,
                option_data,
                ticket_context=ticket_context,
            )
        )

    loading_message = (
        await embed_message.wait(inter, followup=True, ephemeral=True)
        if inter.response.is_done()
        else await embed_message.wait(inter, send=True, ephemeral=True)
    )
    try:
        await open_ticket(
            inter,
            bot,
            panel_data,
            panel_id,
            option_data,
            loading_message,
            ticket_context=ticket_context,
        )
    except (disnake.HTTPException, ValueError) as exc:
        text = str(exc)
        if "limite" in text.lower() and "canal" in text.lower():
            text = "A categoria atingiu o limite de canais. Avise um administrador."
        error = f"{emoji.wrong} Não foi possível criar o ticket: {text}"
        try:
            await loading_message.edit(content=error)
        except Exception:
            await inter.followup.send(error, ephemeral=True)


async def create_ticket_handler(inter: disnake.MessageInteraction, bot, panel_id: str):
    config = db.get_document("tickets_config") or {}
    panel_data = (config.get("panels") or {}).get(panel_id)
    if not panel_data:
        return await inter.response.send_message("Painel de ticket não encontrado.", ephemeral=True)

    if mode_requires_purchase(panel_data):
        options = panel_data.get("options", [])
        option_data = options[0] if len(options) == 1 else None
        return await _send_purchase_selector(inter, panel_id, panel_data, option_data)

    options = panel_data.get("options", [])
    option_data = options[0] if len(options) == 1 else None
    await _initiate_ticket_creation(inter, bot, panel_id, option_data)


async def check_and_create_ticket(
    inter: disnake.Interaction,
    bot: commands.Bot,
    panel_id: str,
    option_data: dict,
):
    config = db.get_document("tickets_config") or {}
    panel_data = (config.get("panels") or {}).get(panel_id)
    if panel_data and mode_requires_purchase(panel_data):
        return await _send_purchase_selector(inter, panel_id, panel_data, option_data)
    await _initiate_ticket_creation(inter, bot, panel_id, option_data)
