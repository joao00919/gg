from __future__ import annotations

import time
import disnake

from functions.database import database as db
from events._common import enviar_log
from functions.emoji import emoji


def _ticket_record(channel_id: int):
    data = db.get_document("tickets_data") or {}
    for panel_id, users in (data.get("panels") or {}).items():
        for owner_id, tickets in (users or {}).items():
            for ticket in tickets or []:
                if int(ticket.get("ticket_id") or 0) == int(channel_id):
                    return str(panel_id), str(owner_id), ticket
    return None, None, None


def _open_count(panel_id: str | None) -> int:
    if not panel_id:
        return 0
    data = db.get_document("tickets_data") or {}
    total = 0
    for tickets in ((data.get("panels") or {}).get(str(panel_id), {}) or {}).values():
        total += sum(1 for ticket in (tickets or []) if ticket.get("status") == "open")
    return total


def _panel_name(panel_id: str | None, fallback: str = "N/A") -> str:
    config = db.get_document("tickets_config") or {}
    panel = ((config.get("panels") or {}).get(str(panel_id)) or {}) if panel_id else {}
    return str(panel.get("name") or fallback)


async def log_ticket_creation(bot, ticket_channel, ticket_owner, panel_name, ticket_mode):
    canais = db.get_document("canais") or {}
    log_channel_id = canais.get("canal_de_logs_de_tickets")
    if not log_channel_id:
        return None

    panel_id, _owner_id, _ticket = _ticket_record(ticket_channel.id)
    mode_label = "Tópico" if str(ticket_mode).lower() in {"topic", "thread", "topico", "tópico"} else "Canal"
    now = int(time.time())
    linhas = [
        f"{emoji.textc} **Painel:** `{_panel_name(panel_id, panel_name)}`",
        f"{emoji.member} **Criador:** {ticket_owner.mention} (`{ticket_owner.id}`)",
        f"{emoji.textc} **Canal/Tópico:** {ticket_channel.mention} (`{ticket_channel.id}`)",
        f"{emoji.ticket} **Modo:** `{mode_label}`",
        f"{emoji.ticket} **Tickets Abertos no Painel:** `{_open_count(panel_id)}`",
        f"{emoji.calendar} **Data/Hora:** <t:{now}:F>",
    ]
    return await enviar_log(ticket_channel.guild, int(log_channel_id), "Log de Tickets - Abertos", linhas)


async def log_ticket_closure(bot, ticket_channel, closed_by, ticket_owner, ticket_mode, reason=None, transcript_url: str | None = None):
    canais = db.get_document("canais") or {}
    log_channel_id = canais.get("canal_de_logs_de_tickets")
    if not log_channel_id:
        return None

    panel_id, owner_id, _ticket = _ticket_record(ticket_channel.id)
    now = int(time.time())
    linhas = [
        f"{emoji.textc} **Painel:** `{_panel_name(panel_id)}`",
        f"{emoji.textc} **Canal/Tópico:** `{ticket_channel.name}` (`{ticket_channel.id}`)",
    ]
    if ticket_owner:
        linhas.append(f"{emoji.member} **Criador:** {ticket_owner.mention} (`{ticket_owner.id}`)")
    elif owner_id:
        linhas.append(f"{emoji.member} **Criador:** <@{owner_id}> (`{owner_id}`)")
    linhas.extend([
        f"{emoji.member} **Fechado por:** {closed_by.mention} (`{closed_by.id}`)",
        f"{emoji.ban} **Motivo:** `{reason or 'Não informado'}`",
        f"{emoji.ticket} **Tickets Abertos no Painel:** `{_open_count(panel_id)}`",
        f"{emoji.calendar} **Data/Hora:** <t:{now}:F>",
    ])

    extra_components = None
    if transcript_url:
        extra_components = [disnake.ui.ActionRow(disnake.ui.Button(
            label="Ver Transcript",
            style=disnake.ButtonStyle.link,
            url=transcript_url,
            emoji=emoji.receipt,
        ))]
    return await enviar_log(
        ticket_channel.guild,
        int(log_channel_id),
        "Log de Tickets - Fechados",
        linhas,
        extra_components=extra_components,
    )


async def log_ticket_reminder(bot, ticket_channel, reminded_by, ticket_owner):
    canais = db.get_document("canais") or {}
    log_channel_id = canais.get("canal_de_logs_de_tickets")
    if not log_channel_id:
        return None
    now = int(time.time())
    linhas = [
        f"{emoji.member} **Lembrado por:** {reminded_by.mention} (`{reminded_by.id}`)",
        f"{emoji.member} **Usuário Lembrado:** {ticket_owner.mention} (`{ticket_owner.id}`)",
        f"{emoji.textc} **Ticket:** {ticket_channel.mention} (`{ticket_channel.id}`)",
        f"{emoji.calendar} **Data/Hora:** <t:{now}:F>",
    ]
    return await enviar_log(ticket_channel.guild, int(log_channel_id), "Log de Tickets - Lembrete", linhas)
