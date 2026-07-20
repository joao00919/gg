from __future__ import annotations

import disnake

from functions.database import database as db
from functions.emoji import emoji
from functions.reviews import save_ticket_review


def _find_ticket(channel_id: int) -> tuple[str | None, dict | None, str | None]:
    data = db.get_document("tickets_data") or {}
    containers = [data.get("panels", {})]
    containers.append({key: value for key, value in data.items() if key not in {"panels", "ai_silenced"}})
    for panels in containers:
        for panel_id, users in (panels or {}).items():
            if not isinstance(users, dict):
                continue
            for user_id, tickets in users.items():
                for ticket in tickets or []:
                    if int(ticket.get("ticket_id", 0) or 0) == int(channel_id):
                        return str(user_id), ticket, str(panel_id)
    return None, None, None


class TicketReviewModal(disnake.ui.Modal):
    def __init__(self, ticket_id: int, owner_id: str, ticket: dict, panel_id: str | None):
        self.ticket_id = ticket_id
        self.owner_id = owner_id
        self.ticket = ticket
        self.panel_id = panel_id
        components = [
            disnake.ui.Label(
                text="Nota de 1 a 5",
                component=disnake.ui.TextInput(
                    custom_id="rating", placeholder="5", min_length=1, max_length=1,
                    style=disnake.TextInputStyle.short, required=True,
                ),
            ),
            disnake.ui.Label(
                text="Comentário",
                component=disnake.ui.TextInput(
                    custom_id="comment", placeholder="Conte como foi o atendimento.",
                    max_length=1000, style=disnake.TextInputStyle.paragraph, required=False,
                ),
            ),
        ]
        super().__init__(title="Avaliar atendimento", custom_id=f"ticket_review_modal:{ticket_id}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        if str(inter.author.id) != self.owner_id:
            await inter.response.send_message(f"{emoji.wrong} Somente o cliente deste ticket pode avaliar.", ephemeral=inter.guild is not None)
            return
        try:
            rating = int(inter.text_values.get("rating", "0"))
            comment = inter.text_values.get("comment", "")
            panel = (db.get_document("tickets_config") or {}).get("panels", {}).get(self.panel_id or "", {})
            save_ticket_review(
                ticket_id=self.ticket_id,
                user_id=inter.author.id,
                staff_id=self.ticket.get("claimed_by") or self.ticket.get("attendant_id") or self.ticket.get("assumed_by"),
                category=self.ticket.get("category") or panel.get("name"),
                rating=rating,
                comment=comment,
            )
            await inter.response.send_message(f"{emoji.correct} Avaliação registrada. Obrigado pelo feedback.", ephemeral=inter.guild is not None)
        except ValueError as exc:
            await inter.response.send_message(f"{emoji.wrong} {exc}", ephemeral=inter.guild is not None)


async def review(inter: disnake.MessageInteraction):
    owner_id, ticket, panel_id = _find_ticket(inter.channel.id)
    if not owner_id or not ticket:
        await inter.response.send_message(f"{emoji.wrong} Este canal não possui um ticket válido.", ephemeral=True)
        return
    if str(inter.author.id) != owner_id:
        await inter.response.send_message(f"{emoji.wrong} Somente o cliente deste ticket pode avaliar.", ephemeral=inter.guild is not None)
        return
    existing = db.get_document("ticket_reviews")
    existing_items = existing if isinstance(existing, list) else (existing or {}).get("items", [])
    if any(item.get("ticketId") == str(inter.channel.id) for item in existing_items):
        await inter.response.send_message(f"{emoji.wrong} Este ticket já foi avaliado.", ephemeral=True)
        return
    await inter.response.send_modal(TicketReviewModal(inter.channel.id, owner_id, ticket, panel_id))


async def review_from_dm(inter: disnake.MessageInteraction, ticket_id: int):
    """Abre a avaliação de um ticket fechado a partir do botão enviado na DM."""
    owner_id, ticket, panel_id = _find_ticket(int(ticket_id))
    is_private = inter.guild is not None

    if not owner_id or not ticket:
        await inter.response.send_message(
            f"{emoji.wrong} Não foi possível localizar os dados deste ticket.",
            ephemeral=is_private,
        )
        return

    if str(inter.author.id) != str(owner_id):
        await inter.response.send_message(
            f"{emoji.wrong} Somente o cliente deste ticket pode avaliar.",
            ephemeral=is_private,
        )
        return

    existing = db.get_document("ticket_reviews")
    existing_items = existing if isinstance(existing, list) else (existing or {}).get("items", [])
    if any(item.get("ticketId") == str(ticket_id) for item in existing_items):
        await inter.response.send_message(
            f"{emoji.wrong} Este ticket já foi avaliado.",
            ephemeral=is_private,
        )
        return

    await inter.response.send_modal(TicketReviewModal(int(ticket_id), str(owner_id), ticket, panel_id))
