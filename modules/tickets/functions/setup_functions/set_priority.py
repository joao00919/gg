from __future__ import annotations

import re

import disnake
from functions.database import database as db
from functions.emoji import emoji
from functions.perms import perms as perms_check
from ..history import log_ticket_event
from ..permissions import check_attendant_permissions, get_attendant_roles
from ...queue import recalculate_queue


PRIORITY_DATA = {
    "normal": {"name": "Normal", "prefix": "normal", "emoji": emoji.verified},
    "high": {"name": "Alta", "prefix": "alta", "emoji": emoji.warn},
    "urgent": {"name": "Urgente", "prefix": "urgente", "emoji": emoji.wrong},
}


class PrioritySelect(disnake.ui.StringSelect):
    def __init__(self, bot):
        self.bot = bot
        options = [
            disnake.SelectOption(label="Prioridade normal", value="normal", emoji=emoji.verified),
            disnake.SelectOption(label="Prioridade alta", value="high", emoji=emoji.warn),
            disnake.SelectOption(label="Prioridade urgente", value="urgent", emoji=emoji.wrong),
        ]
        super().__init__(
            placeholder="Selecione a prioridade do atendimento",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        selected = self.values[0]
        priority = PRIORITY_DATA[selected]

        tickets_data = db.get_document("tickets_data") or {}
        ticket_updated = False
        for users in (tickets_data.get("panels") or {}).values():
            for tickets in (users or {}).values():
                for ticket in tickets or []:
                    if ticket.get("ticket_id") == inter.channel.id:
                        ticket["priority"] = selected
                        ticket_updated = True
                        break
                if ticket_updated:
                    break
            if ticket_updated:
                break

        if not ticket_updated:
            return await inter.edit_original_response(
                content=f"{emoji.wrong} Não foi possível localizar os dados deste ticket.",
                view=None,
            )

        db.save_document("tickets_data", tickets_data)
        await recalculate_queue(self.bot, inter.guild_id)

        current_name = inter.channel.name
        cleaned_name = re.sub(r"^(?:normal|alta|urgente)-", "", current_name, flags=re.IGNORECASE)
        new_name = f"{priority['prefix']}-{cleaned_name}"[:100]
        try:
            await inter.channel.edit(name=new_name)
        except (disnake.Forbidden, disnake.HTTPException):
            pass

        log_ticket_event(
            inter.channel.id,
            "set_priority",
            inter.author.id,
            {"priority": selected},
        )
        await inter.channel.send(
            f"{priority['emoji']} {inter.author.mention} definiu a prioridade como **{priority['name']}**."
        )
        await inter.edit_original_response(
            content=f"{emoji.correct} Prioridade definida como **{priority['name']}**.",
            view=None,
        )


class PrioritySelectView(disnake.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.add_item(PrioritySelect(bot))


async def set_priority(inter: disnake.MessageInteraction, bot):
    if not await check_attendant_permissions(inter.author, inter.channel.id):
        return await inter.response.send_message(
            f"{emoji.wrong} Você não tem permissão para alterar a prioridade.",
            ephemeral=True,
        )

    config = db.get_document("tickets_config") or {}
    tickets_data = db.get_document("tickets_data") or {}
    found_panel_id = None
    for panel_id, users in (tickets_data.get("panels") or {}).items():
        if any(
            ticket.get("ticket_id") == inter.channel.id
            for tickets in (users or {}).values()
            for ticket in (tickets or [])
        ):
            found_panel_id = panel_id
            break

    if not found_panel_id:
        return await inter.response.send_message(
            f"{emoji.wrong} Não foi possível localizar este ticket.",
            ephemeral=True,
        )

    panel_data = (config.get("panels") or {}).get(found_panel_id, {})
    attendant_role_ids = set(get_attendant_roles(panel_data.get("roles", {})))
    member_role_ids = {role.id for role in inter.author.roles}
    is_attendant = bool(attendant_role_ids.intersection(member_role_ids))
    is_bot_admin = await perms_check.check(inter.author.id)
    if not is_attendant and not is_bot_admin:
        return await inter.response.send_message(
            f"{emoji.wrong} Você não tem permissão para alterar a prioridade.",
            ephemeral=True,
        )

    await inter.response.send_message(
        f"{emoji.search} Selecione a nova prioridade do atendimento.",
        view=PrioritySelectView(bot),
        ephemeral=True,
    )
