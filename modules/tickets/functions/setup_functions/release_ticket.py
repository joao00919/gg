from __future__ import annotations

import disnake

from functions.database import database as db
from functions.emoji import emoji
from ..history import log_ticket_event
from ..permissions import check_attendant_permissions
from ...queue import find_ticket_record, recalculate_queue


async def release_ticket(inter: disnake.MessageInteraction, bot) -> None:
    await inter.response.defer(ephemeral=True)

    if not await check_attendant_permissions(inter.author, inter.channel.id):
        return await inter.followup.send(
            f"{emoji.wrong} Você não tem permissão para liberar este atendimento.",
            ephemeral=True,
        )

    _panel_id, owner_id, ticket, tickets_data = find_ticket_record(inter.channel.id)
    if not ticket or ticket.get("status") != "open":
        return await inter.followup.send(
            f"{emoji.wrong} Este canal não possui um ticket aberto.", ephemeral=True
        )

    assigned_id = ticket.get("assigned_to") or ticket.get("assumed_by")
    if not assigned_id:
        return await inter.followup.send(
            f"{emoji.interrogation} Este atendimento ainda não foi assumido.", ephemeral=True
        )

    is_admin = getattr(inter.author.guild_permissions, "administrator", False)
    if int(assigned_id) != int(inter.author.id) and not is_admin:
        return await inter.followup.send(
            f"{emoji.wrong} Apenas o atendente responsável ou um administrador pode sair deste atendimento.",
            ephemeral=True,
        )

    previous_id = int(assigned_id)
    ticket["assigned_to"] = None
    ticket["assumed_by"] = None
    db.save_document("tickets_data", tickets_data)
    log_ticket_event(inter.channel.id, "release", inter.author.id, {"previous_assignee": previous_id})

    await recalculate_queue(bot, inter.guild_id)
    await inter.followup.send(
        f"{emoji.correct} Você saiu do atendimento e o ticket voltou para a fila.",
        ephemeral=True,
    )
    await inter.channel.send(
        f"{emoji.reload} <@{inter.author.id}> liberou este atendimento. O ticket voltou para a fila de suporte.",
        allowed_mentions=disnake.AllowedMentions(users=True, roles=False, everyone=False),
    )

    try:
        owner = inter.guild.get_member(int(owner_id)) if owner_id else None
        if owner is None and owner_id:
            owner = await bot.fetch_user(int(owner_id))
        if owner:
            await owner.send(
                embed=disnake.Embed(
                    title="Atendimento voltou para a fila",
                    description=(
                        f"{emoji.reload} O atendente responsável saiu do ticket `{inter.channel.name}`.\n"
                        "Seu atendimento continua aberto e já voltou para a fila da equipe."
                    ),
                    color=disnake.Color.dark_grey(),
                ),
                components=[disnake.ui.ActionRow(disnake.ui.Button(
                    label="Ir para o ticket",
                    style=disnake.ButtonStyle.link,
                    url=inter.channel.jump_url,
                ))],
            )
    except Exception:
        pass
