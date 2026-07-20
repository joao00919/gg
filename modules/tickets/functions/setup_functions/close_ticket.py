import disnake
from disnake.ext import commands
import asyncio
import time
from disnake.ui import Modal, TextInput
from functions.database import database as db
from functions.transcript_cache import delete_link_from_cache, save_link_to_cache
from ..logs_tickets import log_ticket_closure
from functions.emoji import emoji
import traceback
import os
import io
from ...transcripts import generate_transcript
from ...transcripts.host_transcript import log_transcript, upload_transcript_to_api
from ...utils import SafeFormatter
from ...queue import recalculate_queue

class CloseTicketModal(Modal):
    def __init__(self, bot, channel: disnake.TextChannel, require_reason: bool = False):
        self.bot = bot
        self.channel = channel

        reason_label = "Motivo do Fechamento"
        if not require_reason:
            reason_label += " (Opcional)"
            
        components = [
            TextInput(
                label=reason_label,
                placeholder="Digite o motivo do fechamento do ticket.",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=2000,
                required=require_reason
            )
        ]
        super().__init__(title="Fechar Ticket", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values.get("reason")
        await close_ticket(bot=self.bot, channel=inter.channel, closed_by=inter.author, reason=reason, inter=inter)

async def close_ticket(bot: commands.Bot, channel: disnake.TextChannel, closed_by: disnake.Member, reason: str = None, inter: disnake.Interaction = None):
    if inter:
        await inter.response.defer(ephemeral=True)

    config = db.get_document("tickets_config") or {}
    tickets_data = db.get_document("tickets_data") or {}
    
    found_panel_id = None
    ticket_found = False
    ticket_owner_id = None

    # Procura o ticket e seu dono, e atualiza o status
    for panel_id, users in tickets_data.get("panels", {}).items():
        for user_id, tickets in users.items():
            for ticket in tickets:
                if ticket.get("ticket_id") == channel.id and ticket.get("status") == "open":
                    ticket["status"] = "closed"
                    ticket["closed_at"] = int(time.time())
                    ticket["closed_by"] = closed_by.id
                    ticket["channel_name"] = channel.name
                    if reason:
                        ticket["close_reason"] = reason
                    
                    details = {"channel_name": channel.name}
                    if reason:
                        details["reason"] = reason
                    
                    if "history" not in ticket:
                        ticket["history"] = []
                    
                    event = {
                        "type": "close",
                        "author_id": closed_by.id,
                        "timestamp": int(time.time()),
                        "details": details
                    }
                    ticket["history"].append(event)

                    ticket_found = True
                    ticket_owner_id = user_id
                    found_panel_id = panel_id
                    break
            if ticket_found: break
        if ticket_found: break

    if not ticket_found:
        if inter:
            await inter.followup.send("Este canal não parece ser um ticket aberto.", ephemeral=True)
        return

    # Apaga a call se existir
    call_channel_id = ticket.get("call_channel_id")
    if call_channel_id:
        try:
            call_channel = await bot.fetch_channel(call_channel_id)
            if call_channel:
                await call_channel.delete(reason="Ticket fechado")
        except disnake.NotFound:
            pass # O canal já foi deletado
        except disnake.Forbidden:
            pass # O bot não tem permissão para deletar o canal
        except Exception:
            traceback.print_exc() # Logar outros erros

    # Limpa o status de IA silenciada para este ticket, se houver
    if "ai_silenced" in tickets_data:
        tickets_data["ai_silenced"].pop(str(channel.id), None)

    db.save_document("tickets_data", tickets_data)
    await recalculate_queue(bot, channel.guild.id if channel.guild else None)
    
    panel_data = config.get("panels", {}).get(found_panel_id, {})
    ticket_mode = panel_data.get("mode") or "channel"  # Padrão: channel
    
    ticket_owner = bot.get_user(int(ticket_owner_id)) if ticket_owner_id else None
    if ticket_owner is None and ticket_owner_id:
        try:
            ticket_owner = await bot.fetch_user(int(ticket_owner_id))
        except (disnake.NotFound, disnake.HTTPException):
            ticket_owner = None

    # --- LÓGICA DE TRANSCRIPT COM CACHE ---
    # 1. Limpar cache antigo para garantir que o transcript final seja gerado com todas as mensagens
    delete_link_from_cache(channel.id)

    # 2. Gerar o transcript final antes de deletar o canal
    transcript_file = await generate_transcript(channel, bot)
    
    # 3. Fazer upload do transcript final e salvar no cache (opcional, mas útil para consistência)
    final_transcript_url = None
    transcript_html = None
    if transcript_file:
        transcript_file.fp.seek(0)
        transcript_html = transcript_file.fp.read().decode('utf-8', errors='replace')
        final_transcript_url = await upload_transcript_to_api(transcript_html, channel.name)
        if final_transcript_url:
            save_link_to_cache(channel.id, final_transcript_url)

    # Envia o log de fechamento
    closure_log_message = await log_ticket_closure(bot, channel, closed_by, ticket_owner, ticket_mode, reason, final_transcript_url)

    # O link do transcript já é anexado ao próprio log de fechamento.

    notification_sent = False
    send_dm_pref = panel_data.get("preferences", {}).get("send_close_message", {})
    send_dm_enabled = send_dm_pref.get("enabled", True)

    if ticket_owner and send_dm_enabled:
        close_embed = disnake.Embed(
            title="Ticket fechado",
            description=(
                f"{emoji.correct} Seu atendimento no ticket `{channel.name}` foi finalizado por {closed_by.mention}.\n"
                + (f"**Motivo:** {reason}\n" if reason else "")
                + "O arquivo HTML do transcript está anexado abaixo. Quando disponível, o botão também abre a versão online.\n\n"
                "Você pode deixar uma avaliação sobre o atendimento."
            ),
            color=disnake.Color.dark_grey(),
        )

        buttons = [
            disnake.ui.Button(
                label="Deixe um feedback",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"ticket_review_dm:{channel.id}",
            )
        ]
        if final_transcript_url:
            buttons.append(
                disnake.ui.Button(
                    label="Ver Transcript Online",
                    style=disnake.ButtonStyle.link,
                    url=final_transcript_url,
                )
            )

        payload = {
            "embed": close_embed,
            "components": [disnake.ui.ActionRow(*buttons)],
        }

        if transcript_html is not None:
            transcript_bytes = transcript_html.encode("utf-8")
            payload["file"] = disnake.File(
                fp=io.BytesIO(transcript_bytes),
                filename=f"transcript-{channel.name}.html",
            )

        try:
            await ticket_owner.send(**payload)
            notification_sent = True
        except (disnake.Forbidden, disnake.HTTPException) as exc:
            print(f"[TICKET] Não foi possível enviar a DM de fechamento: {exc}")

    # 4. Limpar o cache após o envio final (o canal será deletado, então o ID não será mais usado)
    delete_link_from_cache(channel.id)

    feedback_message = f"Ticket fechado por {closed_by.mention}. "
    if send_dm_enabled:
        if notification_sent:
            feedback_message += "O usuário foi notificado na DM."
        else:
            feedback_message += "Não foi possível notificar o usuário (DM fechada ou não encontrado)."

    delete_timestamp = int(time.time()) + 5
    if inter:
        await inter.followup.send(f"{feedback_message} Este canal será excluído <t:{delete_timestamp}:R>.")
    
    await asyncio.sleep(5)
    try:
        await channel.delete()
    except disnake.NotFound:
        pass # O canal já foi deletado, então não há nada a fazer.
