import disnake
from disnake.ext import commands

from .create_ticket import create_ticket_handler, _initiate_ticket_creation
from .setup_functions.close_ticket import CloseTicketModal, close_ticket
from functions.database import database as db
from functions.emoji import emoji
from functions.perms import perms
from functions.ai_api import chamar_ia
from .setup_team import AttendantSetupView
from .setup_member import UserSetupView
from . import setup_functions as sfp
from .setup_functions.transfer import transfer_ticket, transfer_attendant_ticket
from .permissions import check_attendant_permissions, get_attendant_roles

from .info import ticket_info
from .setup_functions.show_history import show_history
from .create_ticket import check_and_create_ticket
from .open_ticket import open_ticket
from functions.message import embed_message as message
from modules.tickets.purchase_link import active_ticket_for_purchase, context_from_purchase, find_purchase
BASE_PROMPT_FALLBACK = (
    "Você é ZynxAI, uma assistente virtual amigável e prestativa. Responda de forma direta, útil e educada."
)


class TicketFunctionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _call_ai(self, full_prompt: str) -> str:
        """Chama a API de IA usando a função centralizada com fallback."""
        return await chamar_ia(full_prompt, "Tickets")

    @staticmethod
    def _find_panel_by_channel(channel_id: int) -> tuple[str | None, dict, dict | None]:
        tickets_data = db.get_document("tickets_data") or {} or {}
        panels = (tickets_data.get("panels") or {})
        for panel_id, users in panels.items():
            for _uid, tickets in (users or {}).items():
                for t in (tickets or []):
                    if t.get("ticket_id") == channel_id and t.get("status") == "open":
                        config = db.get_document("tickets_config") or {} or {}
                        panel_data = (config.get("panels") or {}).get(panel_id, {})
                        return panel_id, panel_data, t
        return None, {}, None

    @commands.Cog.listener("on_button_click")
    async def ticket_actions_listener(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        if custom_id.startswith("ticket_review_dm:"):
            try:
                ticket_id = int(custom_id.split(":", 1)[1])
            except (TypeError, ValueError, IndexError):
                return await inter.response.send_message(
                    f"{emoji.wrong} Identificador de ticket inválido.",
                    ephemeral=inter.guild is not None,
                )
            await sfp.review_from_dm(inter, ticket_id)
            return

        if custom_id.startswith("ticket_form_open:"):
            # Handler para abrir formulário após verificação
            parts = custom_id.split(":")
            panel_id = parts[1] if len(parts) >= 2 else None
            option_id = parts[2] if len(parts) >= 3 else None
            
            if not panel_id or not option_id:
                await inter.response.send_message("Erro ao processar solicitação.", ephemeral=True)
                return
            
            config = db.get_document("tickets_config") or {}
            panel_data = config.get("panels", {}).get(panel_id)
            if not panel_data:
                await inter.response.send_message("Painel de ticket não encontrado.", ephemeral=True)
                return
            
            questions = panel_data.get("forms", {}).get(option_id, [])
            if not questions:
                await inter.response.send_message("Formulário não encontrado.", ephemeral=True)
                return
            
            option_data = next((opt for opt in panel_data.get("options", []) if str(opt.get("id")) == str(option_id)), None)
            
            # Abrir modal do formulário
            from .open_ticket import TicketFormModal
            modal = TicketFormModal(inter, self.bot, panel_data, panel_id, questions, option_data)
            await inter.response.send_modal(modal)
            return
        
        if custom_id.startswith("ticket_payment_copy:"):
            token = custom_id.split(":", 1)[1]
            await sfp.copy_ticket_payment(inter, token)

        elif custom_id.startswith("create_ticket_"):
            panel_id = custom_id.split("_")[-1]
            await create_ticket_handler(inter, self.bot, panel_id)
        
        elif custom_id in ["close_ticket", "ticket_close_ticket", "ticket_close_ticket_user"]:
            panel_id, panel_data, _ = self._find_panel_by_channel(inter.channel.id)
            require_reason = panel_data.get("preferences", {}).get("require_reason", {}).get("enabled", False)
            if require_reason:
                await inter.response.send_modal(CloseTicketModal(self.bot, inter.channel, require_reason=True))
            else:
                await close_ticket(bot=self.bot, channel=inter.channel, closed_by=inter.author, inter=inter)

        elif custom_id == "ticket_attendant_setup":
            panel_id, panel_data, ticket_data = self._find_panel_by_channel(inter.channel.id)
            if not panel_data:
                return await inter.response.send_message(f"{emoji.wrong} Não foi possível encontrar a configuração para este ticket.", ephemeral=True)
            
            # Verificar permissões usando sistema centralizado
            has_permission = await check_attendant_permissions(inter.author, inter.channel.id)
            if not has_permission:
                return await inter.response.send_message(f"{emoji.wrong} Você não tem permissão para usar este botão.", ephemeral=True)
            
            option_id = ticket_data.get("option_id")
            option_data = next((opt for opt in panel_data.get("options", []) if str(opt.get("id")) == str(option_id)), None) if option_id else None
            
            view = AttendantSetupView(panel_data, option_data)
            if not view.children:
                await inter.response.send_message("Essa função está desativada.", ephemeral=True)
            else:
                await inter.response.send_message(view=view, ephemeral=True)

        elif custom_id == "ticket_user_setup":
            panel_id, panel_data, ticket_data = self._find_panel_by_channel(inter.channel.id)
            if not panel_data:
                return await inter.response.send_message(f"{emoji.wrong} Não foi possível encontrar a configuração para este ticket.", ephemeral=True)

            option_id = ticket_data.get("option_id")
            option_data = next((opt for opt in panel_data.get("options", []) if str(opt.get("id")) == str(option_id)), None) if option_id else None
            
            view = UserSetupView(panel_data, option_data)
            if not view.children:
                await inter.response.send_message("Essa função está desativada.", ephemeral=True)
            else:
                await inter.response.send_message(view=view, ephemeral=True)

        elif custom_id == "ticket_info":
            await ticket_info(inter)
        
        elif custom_id == "ticket_rename":
            await sfp.rename_ticket(inter)
        
        elif custom_id == "ticket_set_priority":
            await sfp.set_priority(inter, self.bot)

        elif custom_id == "ticket_resolved":
            await sfp.resolved_ticket(inter)
            
        elif custom_id == "ticket_claim":
            await sfp.assume_ticket(inter)

        elif custom_id == "ticket_release":
            await sfp.release_ticket(inter, self.bot)
            
        elif custom_id == "ticket_add_user":
            await sfp.add_user(inter)
            
        elif custom_id == "ticket_remove_user":
            await sfp.remove_user(inter)
            
        elif custom_id == "ticket_notify":
            await sfp.notify(inter)
            
        elif custom_id == "ticket_create_call":
            await sfp.create_call(inter)
            
        elif custom_id == "ticket_transcript":
            await sfp.transcript(inter, self.bot)
            
        elif custom_id == "ticket_history":
            await sfp.show_history(inter)
            
        elif custom_id == "ticket_notes":
            await sfp.notes(inter)
            
        elif custom_id == "ticket_transfer":
            await transfer_attendant_ticket(inter)
        
        elif custom_id == "ticket_payment":
            await sfp.generate_pay(inter, self.bot)
            
        elif custom_id == "ticket_add_user_user":
            await sfp.add_user(inter)
            
        elif custom_id == "ticket_remove_user_user":
            await sfp.remove_user(inter)
            
        elif custom_id == "ticket_transcript_user":
            await sfp.transcript(inter, self.bot)
            
        elif custom_id == "ticket_review":
            await sfp.review(inter)
            
        elif custom_id == "ticket_notify_user":
            await sfp.notify(inter)
            
        elif custom_id == "ticket_transfer_user":
            await transfer_ticket(inter)
            
        elif custom_id == "ticket_payment_user":
            await sfp.generate_pay(inter, self.bot)

        elif custom_id == "ticket_request_call_user":
            await sfp.request_call(inter)
            
        elif custom_id == "ticket_approve_call_request":
            await sfp.approve_call_request(inter)
            
        elif custom_id == "ticket_archive":
            await sfp.archive_ticket(inter)
            
        elif custom_id == "ticket_unarchive":
            await sfp.unarchive_ticket(inter)

    @commands.Cog.listener("on_dropdown")
    async def ticket_dropdown_listener(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id

        if custom_id.startswith("ticket_purchase_select:"):
            parts = custom_id.split(":", 2)
            panel_id = parts[1] if len(parts) > 1 else ""
            option_id = parts[2] if len(parts) > 2 and parts[2] != "-" else None
            config = db.get_document("tickets_config") or {}
            panel_data = (config.get("panels") or {}).get(panel_id)
            if not panel_data:
                return await inter.response.send_message("Painel de ticket não encontrado.", ephemeral=True)

            selected = inter.values[0]
            option_data = None
            if option_id:
                option_data = next(
                    (item for item in panel_data.get("options", []) if str(item.get("id")) == str(option_id)),
                    None,
                )

            if selected == "__without_purchase__":
                context = context_from_purchase(panel_data, None, no_purchase=True)
            else:
                purchase = find_purchase(inter.user.id, selected)
                if not purchase:
                    return await inter.response.send_message(
                        f"{emoji.wrong} Essa compra não foi encontrada no seu histórico.",
                        ephemeral=True,
                    )
                existing = active_ticket_for_purchase(inter.guild, inter.user.id, selected)
                if existing:
                    return await inter.response.send_message(
                        f"{emoji.interrogation} Já existe um atendimento aberto para essa compra.",
                        ephemeral=True,
                        components=[disnake.ui.ActionRow(disnake.ui.Button(
                            label="Ir para ticket",
                            style=disnake.ButtonStyle.link,
                            url=existing.jump_url,
                            emoji=emoji.back,
                        ))],
                    )
                context = context_from_purchase(panel_data, purchase)

            return await _initiate_ticket_creation(
                inter, self.bot, panel_id, option_data, ticket_context=context
            )

        if not custom_id.startswith("ticket_panel_option_select_"):
            return
        
        panel_id = custom_id.replace("ticket_panel_option_select_", "")
        option_id = inter.values[0]

        config = db.get_document("tickets_config") or {}
        panel_data = config.get("panels", {}).get(panel_id)
        if not panel_data:
            if inter.response.is_done():
                await inter.followup.send("Painel de ticket não encontrado.", ephemeral=True)
            else:
                await inter.response.send_message("Painel de ticket não encontrado.", ephemeral=True)
            return

        options = panel_data.get("options", [])
        selected_option = next((opt for opt in options if str(opt.get("id")) == option_id), None)
        if not selected_option:
            if inter.response.is_done():
                await inter.followup.send("Opção selecionada inválida.", ephemeral=True)
            else:
                await inter.response.send_message("Opção selecionada inválida.", ephemeral=True)
            return

        await check_and_create_ticket(inter, self.bot, panel_id, selected_option)

    @commands.Cog.listener("on_message")
    async def on_ticket_message(self, message: disnake.Message):
        if message.author.bot:
            return

        tickets_data = db.get_document("tickets_data") or {}
        ticket_found = False
        channel_id = None

        if message.guild:
            panel_id, panel_data, ticket_data = self._find_panel_by_channel(message.channel.id)
            if panel_id:
                channel_id = message.channel.id
        
        if channel_id:
            for panel in tickets_data.get("panels", {}).values():
                for ticket_owner_id, user_tickets in panel.items():
                    for ticket in user_tickets:
                        if ticket.get("ticket_id") == channel_id and ticket.get("status") == "open":
                            now_ts = int(message.created_at.timestamp())
                            ticket["last_activity_timestamp"] = now_ts
                            is_staff_reply = False
                            if str(message.author.id) != str(ticket_owner_id):
                                try:
                                    is_staff_reply = await check_attendant_permissions(
                                        message.author, message.channel.id
                                    )
                                except Exception:
                                    is_staff_reply = False
                            if is_staff_reply:
                                ticket["last_staff_response_timestamp"] = now_ts
                                ticket["stale_alerted_at"] = None
                            ticket_found = True
                            break
                    if ticket_found: break
                if ticket_found: break
            
            if ticket_found:
                db.save_document("tickets_data", tickets_data)

        tickets_data = db.get_document("tickets_data") or {} or {}
        data_changed = False

        # --- Guild Channel: Staff or User sending a message ---
        if not message.guild:
            return

        panel_id, panel_data, ticket_data = self._find_panel_by_channel(message.channel.id)
        if not panel_id or not panel_data or not panel_data.get("ai_enabled", False):
            if data_changed: db.save_document("tickets_data", tickets_data)
            return

        ticket_id_to_check = str(message.channel.id)
        
        ai_silenced_map = tickets_data.setdefault("ai_silenced", {})
        if ai_silenced_map.get(ticket_id_to_check):
            if data_changed: db.save_document("tickets_data", tickets_data)
            return

        option_id = ticket_data.get("option_id")
        option_data = next((opt for opt in panel_data.get("options", []) if str(opt.get("id")) == str(option_id)), None) if option_id else None

        roles_config = {}
        if option_data:
            roles_config = option_data.get("roles", {})
        else:
            roles_config = panel_data.get("roles", {})

        atendentes_roles = get_attendant_roles(roles_config)
        is_atendente = isinstance(message.author, disnake.Member) and any(
            r.id in atendentes_roles for r in (message.author.roles or [])
        )

        mode = db.get_document("custom_mode").get("mode")
        primary_color_hex = db.get_document("custom_colors").get("primary")
        
        message_content = (
            f"{emoji.wand} **ZynxAI pausada para este ticket.**\n"
            f"{emoji.member} Um atendente já respondeu. A IA não responderá mais aqui."
        )

        if is_atendente:
            ai_silenced_map[ticket_id_to_check] = True
            data_changed = True
            try:
                if mode == "components":
                    container_kwargs = {}
                    if primary_color_hex:
                        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
                    await message.channel.send(
                        components=[
                            disnake.ui.Container(
                                disnake.ui.TextDisplay(message_content),
                                **container_kwargs
                            ),
                            disnake.ui.ActionRow(
                                disnake.ui.Button(
                                    label="Mensagem do Sistema",
                                    style=disnake.ButtonStyle.grey,
                                    disabled=True,
                                    custom_id="TicketAI_SystemBadge"
                                )
                            )
                        ],
                        flags=disnake.MessageFlags(is_components_v2=True)
                    )
                else:
                    embed_kwargs = {}
                    if primary_color_hex:
                        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)
                    embed = disnake.Embed(
                        description=message_content,
                        **embed_kwargs
                    )
                    system_badge = disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Mensagem do Sistema",
                            style=disnake.ButtonStyle.grey,
                            disabled=True,
                            custom_id="TicketAI_SystemBadge"
                        )
                    )
                    await message.channel.send(embed=embed, components=[system_badge])

            except Exception: pass
        
        else:
            user_text = (message.content or "").strip()
            if not user_text:
                if data_changed: db.save_document("tickets_data", tickets_data)
                return

            prompt_config = panel_data.get("ai_prompt") or BASE_PROMPT_FALLBACK
            full_prompt = f"{prompt_config}\n\nUsuário: {user_text}\nAssistente:"
            ai_text = await self._call_ai(full_prompt)
            if not ai_text:
                if data_changed: db.save_document("tickets_data", tickets_data)
                return

            ai_text = ai_text[:1900]
            try:
                await message.reply(ai_text, allowed_mentions=disnake.AllowedMentions.none())
            except Exception:
                try:
                    await message.channel.send(ai_text, allowed_mentions=disnake.AllowedMentions.none())
                except Exception: pass
        
        if data_changed:
            db.save_document("tickets_data", tickets_data)


def setup(bot: commands.Bot):
    bot.add_cog(TicketFunctionsCog(bot))
