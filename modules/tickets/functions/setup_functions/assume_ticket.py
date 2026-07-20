import disnake
from functions.database import database as db
from functions.perms import perms as perms_check
from functions.emoji import emoji
from ..history import log_ticket_event
from ...utils import SafeFormatter
from ..permissions import check_attendant_permissions, get_attendant_roles
from ...queue import recalculate_queue

async def assume_ticket(inter: disnake.MessageInteraction):
    await inter.response.defer(ephemeral=True)
    
    # Verificar permissões
    has_permission = await check_attendant_permissions(inter.author, inter.channel.id)
    if not has_permission:
        return await inter.followup.send(
            f"{emoji.wrong} Você não tem permissão para usar este comando.",
            ephemeral=True
        )

    channel = inter.channel
    config = db.get_document("tickets_config") or {}
    tickets_data = db.get_document("tickets_data") or {}

    found_panel_id = None
    ticket_owner_id = None
    ticket_info = None

    for panel_id, users in tickets_data.get("panels", {}).items():
        for user_id, tickets in users.items():
            for ticket in tickets:
                if ticket.get("ticket_id") == channel.id:
                    found_panel_id = panel_id
                    ticket_owner_id = user_id
                    ticket_info = ticket
                    break
            if found_panel_id:
                break
        if found_panel_id:
            break
            
    if not found_panel_id or not ticket_info:
        return await inter.followup.send("Não foi possível encontrar os dados deste ticket.", ephemeral=True)

    panel_data = config.get("panels", {}).get(found_panel_id)
    if not panel_data:
        return await inter.followup.send("Não foi possível encontrar a configuração do painel associado.", ephemeral=True)

    roles_data = panel_data.get("roles", {})
    atendentes_roles_ids = get_attendant_roles(roles_data)
    user_roles_ids = [role.id for role in inter.author.roles]
    is_atendente = any(role_id in atendentes_roles_ids for role_id in user_roles_ids)
    is_bot_admin = await perms_check.check(inter.author.id)

    if not is_atendente and not is_bot_admin:
        return await inter.followup.send("Você não tem permissão para assumir este ticket.", ephemeral=True)

    if ticket_info.get("assumed_by"):
        if ticket_info["assumed_by"] == inter.author.id:
            return await inter.followup.send("Você já assumiu este ticket.", ephemeral=True)
        else:
            assignee = inter.guild.get_member(ticket_info["assumed_by"])
            return await inter.followup.send(f"Este ticket já foi assumido por {assignee.mention if assignee else 'outro atendente'}.", ephemeral=True)

    ticket_info["assumed_by"] = inter.author.id
    ticket_info["assigned_to"] = inter.author.id
    ticket_info["queue_position"] = 0
    db.save_document("tickets_data", tickets_data)
    
    log_ticket_event(inter.channel.id, "assume", inter.author.id)
    await recalculate_queue(inter.bot, inter.guild_id)

    messages = panel_data.get("messages", {})
    message_template = messages.get("assume_message", "{autor_mention} assumiu o atendimento deste ticket.")
    message_template = str(message_template).replace("<:online:1525583691491836076>", str(emoji.online))
    
    ticket_owner = inter.guild.get_member(int(ticket_owner_id))

    placeholders = SafeFormatter(
        autor_mention=inter.author.mention,
        autor_name=inter.author.name,
        channel_name=channel.name,
        guild_name=inter.guild.name,
        user_mention=ticket_owner.mention if ticket_owner else "usuário desconhecido",
        user_name=ticket_owner.name if ticket_owner else "usuário desconhecido"
    )
    formatted_message = message_template.format_map(placeholders)

    await inter.followup.send("Você assumiu este ticket com sucesso!", ephemeral=True)
    await channel.send(formatted_message)

    try:
        ticket_owner = ticket_owner or await inter.guild.fetch_member(int(ticket_owner_id))
        if ticket_owner:
            dm_embed = disnake.Embed(
                title="Ticket assumido",
                description=(
                    f"• O ticket foi assumido por {inter.author.mention}.\n"
                    "• Redirecione para o canal de suporte clicando no botão abaixo."
                ),
                color=disnake.Color.dark_grey(),
            )
            button = disnake.ui.Button(
                label="Ir até o suporte",
                style=disnake.ButtonStyle.link,
                url=channel.jump_url,
            )
            await ticket_owner.send(embed=dm_embed, components=[button])
    except disnake.Forbidden:
        owner_mention = ticket_owner.mention if ticket_owner else f"<@{ticket_owner_id}>"
        await channel.send(
            f"{owner_mention}, não foi possível te notificar na DM que um atendente assumiu seu ticket. "
            "Verifique suas configurações de privacidade.",
            delete_after=15,
        )
    except Exception as exc:
        print(f"[TICKET] Não foi possível enviar a DM de ticket assumido: {exc}")
