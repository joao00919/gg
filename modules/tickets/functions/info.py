from __future__ import annotations

import time

import disnake
from functions.database import database as db
from functions.emoji import emoji
from modules.tickets.purchase_link import TICKET_MODES, money, order_reference


PRIORITY_LABELS = {
    "normal": "Normal",
    "high": "Alta",
    "urgent": "Urgente",
    # Compatibilidade com tickets antigos.
    "medium": "Alta",
}


async def ticket_info(inter: disnake.MessageInteraction):
    await inter.response.defer(ephemeral=True)

    tickets_data = db.get_document("tickets_data") or {}
    ticket = None
    owner_id = None
    for users in (tickets_data.get("panels") or {}).values():
        for stored_owner_id, tickets in (users or {}).items():
            ticket = next(
                (item for item in (tickets or []) if item.get("ticket_id") == inter.channel.id),
                None,
            )
            if ticket:
                owner_id = stored_owner_id
                break
        if ticket:
            break

    if not ticket or not owner_id:
        return await inter.followup.send(
            f"{emoji.wrong} Não foi possível localizar os dados deste ticket.",
            ephemeral=True,
        )

    owner = inter.guild.get_member(int(owner_id))
    owner_text = owner.mention if owner else f"<@{owner_id}>"
    created_at = int(ticket.get("created_at") or time.time())
    waiting_seconds = max(0, int(time.time()) - created_at)
    waiting_minutes = waiting_seconds // 60

    assigned_id = ticket.get("assigned_to") or ticket.get("assumed_by")
    assigned = inter.guild.get_member(int(assigned_id)) if assigned_id else None
    assigned_text = assigned.mention if assigned else "`Não assumido`"
    priority = PRIORITY_LABELS.get(str(ticket.get("priority") or "normal"), "Normal")
    mode = TICKET_MODES.get(ticket.get("ticket_mode", "common"), "Ticket comum")
    purchase = ticket.get("purchase") or {}
    purchase_id = ticket.get("purchase_id")

    lines = [
        f"{emoji.relations} **Cliente:** {owner_text}",
        f"{emoji.interrogation} **Tipo:** `{mode}`",
        f"{emoji.search} **Prioridade:** `{priority}`",
        f"{emoji.verified} **Atendente responsável:** {assigned_text}",
        f"{emoji.relations} **Posição na fila:** `{ticket.get('queue_position', 1)}`",
        f"{emoji.calendar} **Aberto em:** <t:{created_at}:f>",
        f"{emoji.calendar} **Tempo aguardando:** `{waiting_minutes} minuto(s)`",
    ]
    if purchase_id:
        pricing = purchase.get("pricing") or {}
        product = purchase.get("product") or {}
        lines.extend([
            "",
            "**Compra vinculada**",
            f"{emoji.unlock} Pedido: `{order_reference(purchase or {'purchase_id': purchase_id})}`",
            f"{emoji.cardbox} Produto: `{product.get('name') or 'Não informado'}`",
            f"{emoji.coin} Valor: `{money(pricing.get('final_price'))}`",
        ])

    mode_config = (db.get_document("custom_mode") or {}).get("mode", "components")
    color_hex = (db.get_document("custom_colors") or {}).get("primary")
    if mode_config == "embed":
        kwargs = {}
        if color_hex:
            try:
                kwargs["color"] = disnake.Color(int(color_hex.lstrip("#"), 16))
            except (ValueError, TypeError):
                pass
        return await inter.followup.send(
            embed=disnake.Embed(
                title="Informações do atendimento",
                description="\n".join(lines),
                **kwargs,
            ),
            ephemeral=True,
        )

    container_kwargs = {}
    if color_hex:
        try:
            container_kwargs["accent_colour"] = disnake.Colour(int(color_hex.lstrip("#"), 16))
        except (ValueError, TypeError):
            pass
    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {emoji.z0} Informações do atendimento"),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay("\n".join(lines)),
        **container_kwargs,
    )
    await inter.followup.send(
        components=[container],
        ephemeral=True,
        flags=disnake.MessageFlags(is_components_v2=True),
    )
