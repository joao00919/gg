import disnake
import aiohttp
import io
import re
import time
import asyncio

from functions.emoji import emoji
from disnake.ext import commands
from functions.database import database as db
from functions.message import embed_message
from .ticket_checks import check_office_hours, check_permissions, check_existing_ticket
from modules.tickets.config.container_utils import ContainerUtils
from .logs_tickets import log_ticket_creation
from functions.utils import utils
from .permissions import get_attendant_roles
from modules.tickets.purchase_link import purchase_summary
from modules.tickets.queue import calculate_position, recalculate_queue


class TicketFormModal(disnake.ui.Modal):
    def __init__(self, inter: disnake.Interaction, bot: commands.Bot, panel_data: dict, panel_id: str, questions: list, option_data: dict = None, ticket_context: dict | None = None):
        self.inter = inter
        self.bot = bot
        self.panel_data = panel_data
        self.panel_id = panel_id
        self.option_data = option_data
        self.questions = questions
        self.ticket_context = ticket_context or {}

        components = []
        for question in questions:
            style = disnake.TextInputStyle.paragraph if question.get("style") == "paragraph" else disnake.TextInputStyle.short
            components.append(
                disnake.ui.TextInput(
                    label=question["label"],
                    custom_id=question["id"],
                    style=style,
                    placeholder=question.get("placeholder"),
                    required=question.get("required", True),
                    max_length=500
                )
            )

        super().__init__(title="Responda para Abrir o Ticket", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        # Garantir que emoji está disponível
        from functions.emoji import emoji
        
        # Fazer defer imediatamente para não expirar a interação durante verificações async
        if not inter.response.is_done():
            await inter.response.defer(ephemeral=True)
        
        # Mostrar mensagem de carregamento enquanto verifica
        loading_msg = await inter.followup.send(f"{emoji.loading} Verificando informações...", ephemeral=True)
        
        # Verificações LENTAS (OAuth2, horário, permissões, ticket existente)
        try:
            # Verificar se a verificação OAuth2 é obrigatória
            from modules.cloud.verification_check import is_verification_required, send_verification_required_message, is_user_verified
            
            if is_verification_required():
                # Verificar se o usuário está verificado na database antes de criar o ticket
                if isinstance(inter.user, disnake.Member):
                    member = inter.user
                elif inter.guild:
                    member = inter.guild.get_member(inter.user.id)
                else:
                    member = None
                
                if member:
                    verified = await is_user_verified(member)
                    if not verified:
                        # Deletar mensagem de loading e enviar mensagem de verificação
                        try:
                            await loading_msg.delete()
                        except:
                            pass
                        await send_verification_required_message(inter)
                        # Resetar o painel para remover valores selecionados dos selects
                        try:
                            if isinstance(self.inter, disnake.MessageInteraction) and hasattr(self.inter, 'message') and self.inter.message:
                                await reset_panel_message(self.inter, self.panel_data, self.panel_id)
                            elif hasattr(inter, 'channel') and inter.channel and inter.guild:
                                # Buscar mensagens recentes do bot no canal que contenham o painel
                                async for msg in inter.channel.history(limit=20):
                                    if msg.author == inter.guild.me and msg.components:
                                        # Verificar se é a mensagem do painel procurando pelos custom_ids
                                        is_panel = False
                                        for component in msg.components:
                                            if isinstance(component, disnake.ui.ActionRow):
                                                for item in component.children:
                                                    if hasattr(item, 'custom_id'):
                                                        custom_id = item.custom_id
                                                        if custom_id == f"create_ticket_{self.panel_id}" or custom_id == f"ticket_panel_option_select_{self.panel_id}":
                                                            is_panel = True
                                                            break
                                                if is_panel:
                                                    break
                                        if is_panel:
                                            # Criar objeto fake com message para resetar
                                            class FakeInter:
                                                def __init__(self, msg, guild):
                                                    self.message = msg
                                                    self.guild = guild
                                            
                                            fake_inter = FakeInter(msg, inter.guild)
                                            await reset_panel_message(fake_inter, self.panel_data, self.panel_id)
                                            break
                        except Exception as e:
                            print(f"Erro ao resetar painel após mostrar mensagem de verificação no modal: {e}")
                        return
        except Exception as e:
            # Se houver erro na verificação, continuar normalmente (não bloquear)
            import traceback
            print(f"Erro ao verificar verificação OAuth2 no modal: {e}")
            traceback.print_exc()
        
        form_answers = {q["id"]: inter.text_values[q["id"]] for q in self.questions}
        
        # Verificações de horário, permissões e ticket existente
        ok, error_msg = await check_office_hours(inter, self.panel_data)
        if not ok:
            await loading_msg.edit(content=error_msg)
            # Resetar o painel quando verificação falhar
            try:
                if isinstance(self.inter, disnake.MessageInteraction) and hasattr(self.inter, 'message') and self.inter.message:
                    await reset_panel_message(self.inter, self.panel_data, self.panel_id)
                elif hasattr(inter, 'channel') and inter.channel and inter.guild:
                    # Buscar mensagens recentes do bot no canal que contenham o painel
                    async for msg in inter.channel.history(limit=20):
                        if msg.author == inter.guild.me and msg.components:
                            # Verificar se é a mensagem do painel procurando pelos custom_ids
                            is_panel = False
                            for component in msg.components:
                                if isinstance(component, disnake.ui.ActionRow):
                                    for item in component.children:
                                        if hasattr(item, 'custom_id'):
                                            custom_id = item.custom_id
                                            if custom_id == f"create_ticket_{self.panel_id}" or custom_id == f"ticket_panel_option_select_{self.panel_id}":
                                                is_panel = True
                                                break
                                    if is_panel:
                                        break
                            if is_panel:
                                # Criar objeto fake com message para resetar
                                class FakeInter:
                                    def __init__(self, msg, guild):
                                        self.message = msg
                                        self.guild = guild
                                
                                fake_inter = FakeInter(msg, inter.guild)
                                await reset_panel_message(fake_inter, self.panel_data, self.panel_id)
                                break
            except Exception as e:
                print(f"Erro ao resetar painel após falha em verificação: {e}")
            return

        ok, error_msg = await check_permissions(inter, self.panel_data, self.option_data)
        if not ok:
            await loading_msg.edit(content=error_msg)
            # Resetar o painel quando verificação falhar
            try:
                if isinstance(self.inter, disnake.MessageInteraction) and hasattr(self.inter, 'message') and self.inter.message:
                    await reset_panel_message(self.inter, self.panel_data, self.panel_id)
                elif hasattr(inter, 'channel') and inter.channel and inter.guild:
                    # Buscar mensagens recentes do bot no canal que contenham o painel
                    async for msg in inter.channel.history(limit=20):
                        if msg.author == inter.guild.me and msg.components:
                            # Verificar se é a mensagem do painel procurando pelos custom_ids
                            is_panel = False
                            for component in msg.components:
                                if isinstance(component, disnake.ui.ActionRow):
                                    for item in component.children:
                                        if hasattr(item, 'custom_id'):
                                            custom_id = item.custom_id
                                            if custom_id == f"create_ticket_{self.panel_id}" or custom_id == f"ticket_panel_option_select_{self.panel_id}":
                                                is_panel = True
                                                break
                                    if is_panel:
                                        break
                            if is_panel:
                                # Criar objeto fake com message para resetar
                                class FakeInter:
                                    def __init__(self, msg, guild):
                                        self.message = msg
                                        self.guild = guild
                                
                                fake_inter = FakeInter(msg, inter.guild)
                                await reset_panel_message(fake_inter, self.panel_data, self.panel_id)
                                break
            except Exception as e:
                print(f"Erro ao resetar painel após falha em verificação: {e}")
            return

        ok, error_msg = (True, None)
        if not self.ticket_context.get("purchase_id"):
            ok, error_msg = await check_existing_ticket(inter, self.bot, self.panel_id)
        if not ok:
            await loading_msg.edit(content=error_msg)
            # Resetar o painel quando verificação falhar
            try:
                if isinstance(self.inter, disnake.MessageInteraction) and hasattr(self.inter, 'message') and self.inter.message:
                    await reset_panel_message(self.inter, self.panel_data, self.panel_id)
                elif hasattr(inter, 'channel') and inter.channel and inter.guild:
                    # Buscar mensagens recentes do bot no canal que contenham o painel
                    async for msg in inter.channel.history(limit=20):
                        if msg.author == inter.guild.me and msg.components:
                            # Verificar se é a mensagem do painel procurando pelos custom_ids
                            is_panel = False
                            for component in msg.components:
                                if isinstance(component, disnake.ui.ActionRow):
                                    for item in component.children:
                                        if hasattr(item, 'custom_id'):
                                            custom_id = item.custom_id
                                            if custom_id == f"create_ticket_{self.panel_id}" or custom_id == f"ticket_panel_option_select_{self.panel_id}":
                                                is_panel = True
                                                break
                                    if is_panel:
                                        break
                            if is_panel:
                                # Criar objeto fake com message para resetar
                                class FakeInter:
                                    def __init__(self, msg, guild):
                                        self.message = msg
                                        self.guild = guild
                                
                                fake_inter = FakeInter(msg, inter.guild)
                                await reset_panel_message(fake_inter, self.panel_data, self.panel_id)
                                break
            except Exception as e:
                print(f"Erro ao resetar painel após falha em verificação: {e}")
            return

        # Não deletar a mensagem de loading - ela será editada com a mensagem de sucesso
        try:
            await _finish_ticket_creation(
                inter, self.bot, self.panel_data, self.panel_id,
                option_data=self.option_data,
                form_answers=form_answers,
                loading_message=loading_msg,
                ticket_context=self.ticket_context
            )
            # Resetar a mensagem do painel original
            # Se self.inter tem message (interação original), usar ela
            # Caso contrário, buscar a mensagem do painel no canal
            try:
                if isinstance(self.inter, disnake.MessageInteraction) and hasattr(self.inter, 'message') and self.inter.message:
                    await reset_panel_message(self.inter, self.panel_data, self.panel_id)
                elif hasattr(inter, 'channel') and inter.channel and inter.guild:
                    # Buscar mensagens recentes do bot no canal que contenham o painel
                    async for msg in inter.channel.history(limit=20):
                        if msg.author == inter.guild.me and msg.components:
                            # Verificar se é a mensagem do painel procurando pelos custom_ids
                            is_panel = False
                            for component in msg.components:
                                if isinstance(component, disnake.ui.ActionRow):
                                    for item in component.children:
                                        if hasattr(item, 'custom_id'):
                                            custom_id = item.custom_id
                                            if custom_id == f"create_ticket_{self.panel_id}" or custom_id == f"ticket_panel_option_select_{self.panel_id}":
                                                is_panel = True
                                                break
                                    if is_panel:
                                        break
                            if is_panel:
                                # Criar objeto fake com message para resetar
                                class FakeInter:
                                    def __init__(self, msg, guild):
                                        self.message = msg
                                        self.guild = guild
                                
                                fake_inter = FakeInter(msg, inter.guild)
                                await reset_panel_message(fake_inter, self.panel_data, self.panel_id)
                                break
            except Exception as e:
                print(f"Erro ao resetar painel após criar ticket via modal: {e}")
        except (ValueError, disnake.HTTPException) as e:
            # Garantir que emoji está disponível
            from functions.emoji import emoji
            # Verificar se é erro de limite de canais
            error_message = str(e)
            if "Limite de canais exedido" in error_message or ("maximum" in error_message.lower() and "channel" in error_message.lower()):
                error_msg = f"{emoji.wrong} Limite de canais exedido na categoria, contate com administrador."
            elif isinstance(e, ValueError):
                error_msg = f"{emoji.wrong} {str(e)}"
            else:
                error_msg = f"{emoji.wrong} Ocorreu um erro ao criar o ticket: {e}"
            
            try:
                await loading_msg.edit(content=error_msg)
            except:
                await inter.followup.send(content=error_msg, ephemeral=True)
            # Resetar o painel quando erro ocorrer
            try:
                if isinstance(self.inter, disnake.MessageInteraction) and hasattr(self.inter, 'message') and self.inter.message:
                    await reset_panel_message(self.inter, self.panel_data, self.panel_id)
                elif hasattr(inter, 'channel') and inter.channel and inter.guild:
                    # Buscar mensagens recentes do bot no canal que contenham o painel
                    async for msg in inter.channel.history(limit=20):
                        if msg.author == inter.guild.me and msg.components:
                            # Verificar se é a mensagem do painel procurando pelos custom_ids
                            is_panel = False
                            for component in msg.components:
                                if isinstance(component, disnake.ui.ActionRow):
                                    for item in component.children:
                                        if hasattr(item, 'custom_id'):
                                            custom_id = item.custom_id
                                            if custom_id == f"create_ticket_{self.panel_id}" or custom_id == f"ticket_panel_option_select_{self.panel_id}":
                                                is_panel = True
                                                break
                                    if is_panel:
                                        break
                            if is_panel:
                                # Criar objeto fake com message para resetar
                                class FakeInter:
                                    def __init__(self, msg, guild):
                                        self.message = msg
                                        self.guild = guild
                                
                                fake_inter = FakeInter(msg, inter.guild)
                                await reset_panel_message(fake_inter, self.panel_data, self.panel_id)
                                break
            except Exception as reset_error:
                print(f"Erro ao resetar painel após erro: {reset_error}")
        except Exception as e:
            # Garantir que emoji está disponível
            from functions.emoji import emoji
            try:
                await loading_msg.edit(content=f"{emoji.wrong} Ocorreu um erro inesperado: {e}")
            except:
                await inter.followup.send(content=f"{emoji.wrong} Ocorreu um erro inesperado: {e}", ephemeral=True)
            # Resetar o painel quando erro ocorrer
            try:
                if isinstance(self.inter, disnake.MessageInteraction) and hasattr(self.inter, 'message') and self.inter.message:
                    await reset_panel_message(self.inter, self.panel_data, self.panel_id)
                elif hasattr(inter, 'channel') and inter.channel and inter.guild:
                    # Buscar mensagens recentes do bot no canal que contenham o painel
                    async for msg in inter.channel.history(limit=20):
                        if msg.author == inter.guild.me and msg.components:
                            # Verificar se é a mensagem do painel procurando pelos custom_ids
                            is_panel = False
                            for component in msg.components:
                                if isinstance(component, disnake.ui.ActionRow):
                                    for item in component.children:
                                        if hasattr(item, 'custom_id'):
                                            custom_id = item.custom_id
                                            if custom_id == f"create_ticket_{self.panel_id}" or custom_id == f"ticket_panel_option_select_{self.panel_id}":
                                                is_panel = True
                                                break
                                    if is_panel:
                                        break
                            if is_panel:
                                # Criar objeto fake com message para resetar
                                class FakeInter:
                                    def __init__(self, msg, guild):
                                        self.message = msg
                                        self.guild = guild
                                
                                fake_inter = FakeInter(msg, inter.guild)
                                await reset_panel_message(fake_inter, self.panel_data, self.panel_id)
                                break
            except Exception as reset_error:
                print(f"Erro ao resetar painel após erro: {reset_error}")

async def reset_panel_message(inter: disnake.MessageInteraction, panel_data: dict, panel_id: str):
    """Reseta a mensagem do painel removendo valores selecionados dos selects"""
    try:
        if not hasattr(inter, 'message') or not inter.message:
            return
        
        style = panel_data.get("message_style", "embed")
        payload = {}
        options = panel_data.get("options", [])
        action_row = None

        if len(options) > 1:
            select_options = []
            for opt in options:
                try:
                    opt_emoji = opt.get("emoji")
                    parsed_emoji = None
                    if opt_emoji:
                        parsed_emoji = utils.safe_get_emoji(opt_emoji)
                    
                    select_options.append(
                        disnake.SelectOption(
                            label=opt.get("name", "Opção sem nome"),
                            value=str(opt.get("id")),
                            emoji=parsed_emoji,
                            description=opt.get("description")
                        )
                    )
                except Exception:
                    select_options.append(
                        disnake.SelectOption(
                            label=opt.get("name", "Opção sem nome"),
                            value=str(opt.get("id")),
                            emoji=None,
                            description=opt.get("description")
                        )
                    )
            
            select = disnake.ui.StringSelect(
                custom_id=f"ticket_panel_option_select_{panel_id}",
                placeholder="Selecione uma opção para abrir o ticket...",
                options=select_options
            )
            action_row = disnake.ui.ActionRow(select)
        else:
            button_data = panel_data.get("button", {})
            button_style_map = {
                "green": disnake.ButtonStyle.success, "grey": disnake.ButtonStyle.secondary,
                "red": disnake.ButtonStyle.danger, "blue": disnake.ButtonStyle.primary
            }
            
            button_label = button_data.get("label") if button_data.get("label") else "Abrir ticket"
            button_emoji_raw = button_data.get("emoji")
            button_emoji = None
            if button_emoji_raw:
                button_emoji = utils.safe_get_emoji(button_emoji_raw)
            if not button_emoji:
                button_emoji = emoji.mail2
            
            button_style = button_style_map.get(button_data.get("style", "grey").lower(), disnake.ButtonStyle.secondary)
            
            try:
                button = disnake.ui.Button(
                    label=button_label, 
                    emoji=button_emoji,
                    style=button_style, 
                    custom_id=f"create_ticket_{panel_id}"
                )
            except Exception:
                button = disnake.ui.Button(
                    label=button_label, 
                    emoji=None,
                    style=button_style, 
                    custom_id=f"create_ticket_{panel_id}"
                )
            action_row = disnake.ui.ActionRow(button)

        if style == "embed":
            content_data = panel_data.get("embed", {})
            try:
                color_str = content_data.get("color", "#5865F2").lstrip("#")
                color = disnake.Color(int(color_str, 16))
            except (ValueError, TypeError):
                color = disnake.Color.default()

            embed = disnake.Embed(
                title=content_data.get("title"), 
                description=content_data.get("description"),
                color=color
            )
            if image_url := content_data.get("image_url"):
                if "http" in image_url: embed.set_image(url=image_url)
            if thumb_url := content_data.get("thumbnail_url"):
                if "http" in thumb_url: embed.set_thumbnail(url=thumb_url)
            
            payload["embed"] = embed
            payload["components"] = [action_row]
            
        elif style == "content":
            content_data = panel_data.get("content", {})
            payload["content"] = content_data.get("content")
            payload["components"] = [action_row]
            if image_url := content_data.get("image_url"):
                if "http" in image_url:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(image_url) as resp:
                                if resp.status == 200:
                                    image_bytes = await resp.read()
                                    payload["file"] = disnake.File(io.BytesIO(image_bytes), filename="image.png")
                    except Exception:
                        pass
                        
        elif style == "container":
            content_data = panel_data.get("container", {})
            content = content_data.get("content")
            image_url = content_data.get("image_url")
            thumbnail_url = content_data.get("thumbnail_url")
            color_hex = content_data.get("color")

            container = ContainerUtils.montar_container(
                conteudo=content, 
                imagem_url=image_url, 
                cor_hex=color_hex, 
                extra_children=[action_row],
                thumbnail_url=thumbnail_url
            )
            payload["components"] = [container]
            payload["flags"] = disnake.MessageFlags(is_components_v2=True)

        # Editar a mensagem do painel
        try:
            # Verificar se a mensagem ainda existe e está acessível
            if not inter.message:
                return
            
            # Tentar buscar a mensagem novamente para garantir que ainda existe
            try:
                message = await inter.message.channel.fetch_message(inter.message.id)
            except (disnake.NotFound, disnake.HTTPException):
                # Mensagem não existe mais, não podemos editá-la
                return
            
            await message.edit(**payload)
        except (disnake.NotFound, disnake.HTTPException) as e:
            # Mensagem pode ter sido deletada ou não estar mais acessível
            # Não fazer nada, apenas ignorar silenciosamente
            pass
        except Exception as e:
            print(f"Erro inesperado ao resetar painel: {e}")
    except Exception as e:
        # Falha silenciosamente se não conseguir resetar o painel
        print(f"Erro ao resetar painel: {e}")

async def send_opening_message(channel: disnake.TextChannel | disnake.Thread, user: disnake.Member, panel_data: dict, option_data: dict = None, form_answers: dict = None, questions: list = None, ticket_context: dict | None = None, queue_position: int = 1, queue_total: int | None = None, created_at: int | None = None):
    """Envia a abertura no mesmo formato compacto observado na referência.

    O primeiro cartão contém apenas o status do ticket e os acessos aos painéis.
    Mensagens personalizadas e dados de compra continuam disponíveis em mensagens
    separadas, evitando o painel duplicado que existia nas versões anteriores.
    """
    ticket_context = ticket_context or {"ticket_mode": panel_data.get("ticket_mode", "common")}
    created_at = created_at or int(time.time())

    action_row = disnake.ui.ActionRow(
        disnake.ui.Button(
            label="Painel do Atendente",
            emoji=emoji.verified,
            style=disnake.ButtonStyle.grey,
            custom_id="ticket_attendant_setup",
        ),
        disnake.ui.Button(
            label="Painel do Usuário",
            emoji=emoji.relations,
            style=disnake.ButtonStyle.grey,
            custom_id="ticket_user_setup",
        ),
        disnake.ui.Button(
            label="",
            emoji=emoji.interrogation,
            style=disnake.ButtonStyle.grey,
            custom_id="ticket_info",
        ),
    )

    opening_embed = disnake.Embed(
        title="Ticket Aberto",
        description=(
            f"Olá {user.mention}, seu ticket foi aberto com sucesso!\n\n"
            "Aguarde enquanto nossa equipe responde."
        ),
        color=disnake.Color.green(),
        timestamp=disnake.utils.utcnow(),
    )
    summary_message = await channel.send(embed=opening_embed, components=[action_row])

    # Dados de compra ficam em um cartão separado somente quando o ticket está
    # realmente vinculado a um pedido. Tickets comuns permanecem limpos.
    if ticket_context.get("purchase") or ticket_context.get("purchase_id"):
        details_embed = disnake.Embed(
            title="Informações do Atendimento",
            description=purchase_summary(
                ticket_context,
                panel_data,
                queue_position=queue_position,
                queue_total=queue_total,
                created_at=created_at,
            ),
            color=disnake.Color.from_rgb(25, 26, 29),
        )
        await channel.send(embed=details_embed)

    open_message_data = (option_data or {}).get("open_message") or panel_data.get("open_message") or {}
    style = open_message_data.get("style", "embed")

    question_map = {q.get("id"): q.get("label", "Pergunta") for q in (questions or [])}
    form_text = ""
    if form_answers:
        form_text = "\n\n**Respostas do Formulário:**\n" + "\n\n".join(
            f"**{question_map.get(qid, 'Pergunta')}:**\n{answer}"
            for qid, answer in form_answers.items()
        )

    if style == "container":
        data = open_message_data.get("container") or {}
        content = str(data.get("content") or "").strip() + form_text
        if content or data.get("image_url") or data.get("thumbnail_url"):
            container = ContainerUtils.montar_container(
                conteudo=content.strip(),
                imagem_url=data.get("image_url"),
                cor_hex=data.get("color"),
                thumbnail_url=data.get("thumbnail_url"),
            )
            await channel.send(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True),
            )
        return summary_message

    if style == "content":
        data = open_message_data.get("content") or {}
        content = (str(data.get("content") or "").strip() + form_text).strip()
        file_to_send = None
        image_url = data.get("image_url")
        if image_url and str(image_url).startswith(("http://", "https://")):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            file_to_send = disnake.File(io.BytesIO(await resp.read()), filename="image.png")
            except Exception:
                file_to_send = None
        if content or file_to_send:
            await channel.send(content=content or None, file=file_to_send)
        return summary_message

    data = open_message_data.get("embed") or {}
    has_custom_embed = any(data.get(key) for key in ("title", "description", "image_url", "thumbnail_url"))
    if has_custom_embed or form_text:
        color = disnake.Color.from_rgb(25, 26, 29)
        raw_color = str(data.get("color") or "").strip().lstrip("#")
        if len(raw_color) == 6:
            try:
                color = disnake.Color(int(raw_color, 16))
            except ValueError:
                pass
        custom_embed = disnake.Embed(
            title=data.get("title") or ("Informações do Ticket" if form_text else None),
            description=(str(data.get("description") or "").strip() + form_text).strip() or None,
            color=color,
        )
        if data.get("image_url"):
            custom_embed.set_image(url=data["image_url"])
        if data.get("thumbnail_url"):
            custom_embed.set_thumbnail(url=data["thumbnail_url"])
        await channel.send(embed=custom_embed)

    return summary_message


async def open_ticket(inter: disnake.Interaction, bot: commands.Bot, panel_data: dict, panel_id: str, option_data: dict = None, loading_message: disnake.Message = None, ticket_context: dict | None = None):
    # Esta função agora só é chamada depois de um message.wait
    # O chamador lida com as exceções.
    
    # Função auxiliar para editar a mensagem correta
    async def edit_message(content: str):
        if loading_message:
            try:
                await loading_message.edit(content=content)
            except:
                try:
                    await inter.edit_original_message(content=content)
                except:
                    pass
        else:
            try:
                await inter.edit_original_message(content=content)
            except:
                pass
    
    # Mover as checagens para cá para o fluxo sem formulário
    ok, error_msg = await check_office_hours(inter, panel_data)
    if not ok:
        await edit_message(error_msg)
        # Resetar o painel quando verificação falhar
        if isinstance(inter, disnake.MessageInteraction) and hasattr(inter, 'message') and inter.message:
            try:
                await reset_panel_message(inter, panel_data, panel_id)
            except Exception as e:
                print(f"Erro ao resetar painel após falha em verificação: {e}")
        return

    ok, error_msg = await check_permissions(inter, panel_data, option_data)
    if not ok:
        await edit_message(error_msg)
        # Resetar o painel quando verificação falhar
        if isinstance(inter, disnake.MessageInteraction) and hasattr(inter, 'message') and inter.message:
            try:
                await reset_panel_message(inter, panel_data, panel_id)
            except Exception as e:
                print(f"Erro ao resetar painel após falha em verificação: {e}")
        return

    ok, error_msg = (True, None)
    if not (ticket_context or {}).get("purchase_id"):
        ok, error_msg = await check_existing_ticket(inter, bot, panel_id)
    if not ok:
        await edit_message(error_msg)
        # Resetar o painel quando verificação falhar
        if isinstance(inter, disnake.MessageInteraction) and hasattr(inter, 'message') and inter.message:
            try:
                await reset_panel_message(inter, panel_data, panel_id)
            except Exception as e:
                print(f"Erro ao resetar painel após falha em verificação: {e}")
        return

    return await _finish_ticket_creation(inter, bot, panel_data, panel_id, option_data, loading_message=loading_message, ticket_context=ticket_context)


async def _finish_ticket_creation(inter: disnake.Interaction, bot, panel_data: dict, panel_id: str, option_data: dict = None, form_answers: dict = None, loading_message: disnake.Message = None, ticket_context: dict | None = None) -> disnake.TextChannel | disnake.Thread | None:
    user = inter.author
    ticket_context = ticket_context or {"ticket_mode": panel_data.get("ticket_mode", "common")}
    mode = panel_data.get("mode") or "channel"  # Padrão: channel se não configurado
    
    if option_data:
        ticket_name_raw = option_data.get("name", "ticket")
    else:
        ticket_name_raw = panel_data.get("name", "ticket")
        
    # Sanitize panel name for channel naming conventions
    ticket_name = re.sub(r'[^a-z0-9-]', '', ticket_name_raw.lower().replace(' ', '-'))[:25]
    if not ticket_name:
        ticket_name = "ticket"

    new_ticket_channel = None

    if mode == "topic":
        channel_id = panel_data.get("channel_id")
        channel = bot.get_channel(channel_id)
        if not channel or not isinstance(channel, disnake.TextChannel):
            raise ValueError("O canal para criação de tópicos não foi encontrado ou não é um canal de texto.")
        
        new_ticket_channel = await channel.create_thread(
            name=f"{ticket_name}-{user.name}",
            type=disnake.ChannelType.private_thread,
            invitable=False
        )

    elif mode == "channel":
        category_id = panel_data.get("category_id")
        category = bot.get_channel(category_id)
        if not category or not isinstance(category, disnake.CategoryChannel):
            raise ValueError("A categoria para criação de canais não foi encontrada.")

        # Verificar limite de canais na categoria (Discord permite máximo 50 canais por categoria)
        text_channels_in_category = [ch for ch in category.channels if isinstance(ch, disnake.TextChannel)]
        if len(text_channels_in_category) >= 50:
            raise ValueError("Limite de canais exedido na categoria, contate com administrador.")

        roles_data = option_data.get("roles", {}) if option_data else panel_data.get("roles", {})
        atendentes_roles_ids = get_attendant_roles(roles_data)
        overwrites = {
            inter.guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            user: disnake.PermissionOverwrite(read_messages=True, send_messages=True),
            inter.guild.me: disnake.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        for role_id in atendentes_roles_ids:
            role = inter.guild.get_role(role_id)
            if role:
                overwrites[role] = disnake.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            new_ticket_channel = await inter.guild.create_text_channel(
                name=f"{ticket_name}-{user.name}",
                category=category,
                overwrites=overwrites
            )
        except disnake.HTTPException as e:
            # Se o erro for relacionado ao limite de canais, mostrar mensagem específica
            if "maximum" in str(e).lower() or "limit" in str(e).lower() or e.code == 50035:
                raise ValueError("Limite de canais exedido na categoria, contate com administrador.")
            raise

    else:
        raise ValueError(f"Modo de painel desconhecido ou não configurado: '{mode}'.")


    if new_ticket_channel:
        tickets_data = db.get_document("tickets_data") or {}
        user_tickets = tickets_data.setdefault("panels", {}).setdefault(panel_id, {}).setdefault(str(user.id), [])
        
        created_at = int(time.time())
        queue_position = 1
        queue_total = 1
        ticket_payload = {
            "ticket_id": new_ticket_channel.id,
            "guild_id": inter.guild.id,
            "status": "open",
            "created_at": created_at,
            "last_activity_timestamp": created_at,
            "last_staff_response_timestamp": None,
            "stale_alerted_at": None,
            "ticket_mode": ticket_context.get("ticket_mode", panel_data.get("ticket_mode", "common")),
            "purchase_id": ticket_context.get("purchase_id"),
            "purchase": ticket_context.get("purchase"),
            "purchase_found": bool(ticket_context.get("purchase_id") or ticket_context.get("purchase_found")),
            "priority": ticket_context.get("priority", "normal"),
            "assigned_to": None,
            "queue_position": queue_position,
            "history": [{
                "type": "create",
                "author_id": user.id,
                "timestamp": created_at,
                "details": {"purchase_id": ticket_context.get("purchase_id")}
            }]
        }

        if option_data:
            ticket_payload["option_id"] = option_data.get("id")

        if form_answers:
            ticket_payload["form_answers"] = form_answers

        user_tickets.append(ticket_payload)
        queue_position, queue_total = calculate_position(tickets_data, ticket_payload)
        ticket_payload["queue_position"] = queue_position

        db.save_document("tickets_data", tickets_data)
        
        # Envia o log de criação
        await log_ticket_creation(bot, new_ticket_channel, user, panel_data.get("name", "N/A"), mode)

        questions = []
        if form_answers and option_data:
            option_id = str(option_data.get("id"))
            questions = panel_data.get("forms", {}).get(option_id, [])
        summary_message = await send_opening_message(
            new_ticket_channel,
            user,
            panel_data,
            option_data,
            form_answers,
            questions,
            ticket_context=ticket_context,
            queue_position=queue_position,
            queue_total=queue_total,
            created_at=created_at,
        )
        if summary_message:
            ticket_payload["summary_message_id"] = summary_message.id
            db.save_document("tickets_data", tickets_data)
        await recalculate_queue(bot, inter.guild.id)
        
        # Enviar menção do usuário e dos cargos de atendimento, depois apagar
        mentions = [user.mention]
        roles_data = option_data.get("roles", {}) if option_data else panel_data.get("roles", {})
        atendentes_roles_ids = get_attendant_roles(roles_data)
        if atendentes_roles_ids:
            for role_id in atendentes_roles_ids:
                role = inter.guild.get_role(role_id)
                if role:
                    mentions.append(role.mention)
        
        try:
            mention_msg = await new_ticket_channel.send(" ".join(mentions))
            await asyncio.sleep(2)
            try:
                await mention_msg.delete()
            except:
                pass
        except:
            pass
        
        # Envia a mensagem de sucesso final, editando a mensagem de loading ou a mensagem original
        success_msg = f"{emoji.correct} Atendimento aberto em {new_ticket_channel.mention}."
        if loading_message:
            try:
                await loading_message.edit(content=success_msg)
            except:
                try:
                    await inter.edit_original_message(content=success_msg)
                except:
                    pass
        else:
            try:
                await inter.edit_original_message(content=success_msg)
            except:
                pass
        
        # Resetar a mensagem do painel para remover valores selecionados dos selects
        if isinstance(inter, disnake.MessageInteraction) and hasattr(inter, 'message') and inter.message:
            try:
                await reset_panel_message(inter, panel_data, panel_id)
            except Exception as e:
                # Falha silenciosamente se não conseguir resetar
                print(f"Erro ao resetar painel após criar ticket: {e}")
            
    return new_ticket_channel
