from __future__ import annotations

from typing import Any, Optional

import disnake

from functions.database import database as db

_PRIORITY_WEIGHT = {
    "critical": 4,
    "urgent": 4,
    "high": 3,
    "normal": 2,
    "low": 1,
}


def find_ticket_record(channel_id: int) -> tuple[Optional[str], Optional[str], Optional[dict], dict]:
    """Retorna painel, dono, registro e documento completo do ticket."""
    tickets_data = db.get_document("tickets_data") or {}
    for panel_id, users in (tickets_data.get("panels") or {}).items():
        for user_id, tickets in (users or {}).items():
            for ticket in tickets or []:
                if int(ticket.get("ticket_id") or 0) == int(channel_id):
                    return str(panel_id), str(user_id), ticket, tickets_data
    return None, None, None, tickets_data


def _is_waiting(ticket: dict) -> bool:
    return (
        ticket.get("status") == "open"
        and not (ticket.get("assigned_to") or ticket.get("assumed_by"))
    )


def _priority_weight(ticket: dict) -> int:
    base = _PRIORITY_WEIGHT.get(str(ticket.get("priority") or "normal").lower(), 2)
    # Compra confirmada sempre ganha vantagem sobre um ticket geral da mesma classe.
    return base * 10 + (1 if ticket.get("purchase_id") or ticket.get("purchase_found") else 0)


def _queue_entries(tickets_data: dict, guild_id: Optional[int] = None) -> list[tuple[str, str, dict]]:
    entries: list[tuple[str, str, dict]] = []
    for panel_id, users in (tickets_data.get("panels") or {}).items():
        for user_id, tickets in (users or {}).items():
            for ticket in tickets or []:
                if not _is_waiting(ticket):
                    continue
                if guild_id and int(ticket.get("guild_id") or 0) not in {0, int(guild_id)}:
                    continue
                entries.append((str(panel_id), str(user_id), ticket))
    return sorted(
        entries,
        key=lambda item: (
            -_priority_weight(item[2]),
            int(item[2].get("created_at") or 0),
            int(item[2].get("ticket_id") or 0),
        ),
    )


def calculate_position(tickets_data: dict, target: dict) -> tuple[int, int]:
    if not _is_waiting(target):
        return 0, len(_queue_entries(tickets_data))
    queue = _queue_entries(tickets_data, target.get("guild_id"))
    for index, (_panel_id, _user_id, ticket) in enumerate(queue, start=1):
        if ticket is target or int(ticket.get("ticket_id") or 0) == int(target.get("ticket_id") or 0):
            return index, len(queue)
    return max(1, len(queue)), len(queue)


async def recalculate_queue(bot: Any, guild_id: Optional[int] = None, *, update_messages: bool = True) -> None:
    """Reordena a fila e atualiza os resumos já publicados nos tickets."""
    tickets_data = db.get_document("tickets_data") or {}
    queue = _queue_entries(tickets_data, guild_id)
    changed = False

    for index, (_panel_id, _user_id, ticket) in enumerate(queue, start=1):
        if ticket.get("queue_position") != index:
            ticket["queue_position"] = index
            changed = True

    for panel_users in (tickets_data.get("panels") or {}).values():
        for tickets in (panel_users or {}).values():
            for ticket in tickets or []:
                if ticket.get("status") == "open" and not _is_waiting(ticket):
                    if ticket.get("queue_position") != 0:
                        ticket["queue_position"] = 0
                        changed = True

    if changed:
        db.save_document("tickets_data", tickets_data)

    if not update_messages:
        return

    config = db.get_document("tickets_config") or {}
    from modules.tickets.purchase_link import purchase_summary

    for panel_id, user_id, ticket in [
        item
        for users_panel_id, users in (tickets_data.get("panels") or {}).items()
        for item in [
            (str(users_panel_id), str(owner_id), ticket_item)
            for owner_id, owner_tickets in (users or {}).items()
            for ticket_item in owner_tickets or []
            if ticket_item.get("status") == "open"
        ]
    ]:
        channel_id = int(ticket.get("ticket_id") or 0)
        message_id = int(ticket.get("summary_message_id") or 0)
        if not channel_id or not message_id:
            continue
        if guild_id and int(ticket.get("guild_id") or 0) not in {0, int(guild_id)}:
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                continue
        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            continue

        panel = (config.get("panels") or {}).get(panel_id, {})
        context = {
            "ticket_mode": ticket.get("ticket_mode", panel.get("ticket_mode", "common")),
            "priority": ticket.get("priority", "normal"),
            "purchase_id": ticket.get("purchase_id"),
            "purchase": ticket.get("purchase"),
            "purchase_found": bool(ticket.get("purchase_id") or ticket.get("purchase_found")),
        }
        position, total = calculate_position(tickets_data, ticket)
        assignee_id = ticket.get("assigned_to") or ticket.get("assumed_by")
        description = purchase_summary(
            context,
            panel,
            queue_position=position,
            queue_total=total,
            created_at=int(ticket.get("created_at") or 0),
            assigned_to=int(assignee_id) if assignee_id else None,
        )
        color = disnake.Color.from_rgb(25, 26, 29)
        try:
            await message.edit(embed=disnake.Embed(description=description, color=color))
        except Exception:
            continue
