import asyncio
import disnake
from disnake.ext import commands
import time
from datetime import datetime
from functions.database import database as db
from functions.emoji import emoji
from functions.payments import approve_manual_pix_payment


def _find_cart_by_thread(carts: dict, thread_id: str):
    """Localiza o carrinho mesmo após migrações que usaram outra chave no JSON."""
    wanted = str(thread_id)
    direct = carts.get(wanted)
    if isinstance(direct, dict):
        return wanted, direct
    for cart_key, cart in carts.items():
        if not isinstance(cart, dict):
            continue
        if str(cart.get("thread_id") or cart.get("cart_id") or "") == wanted:
            return str(cart_key), cart
    return None, None


class CancelCheckout(commands.Cog):
    """Gerencia cancelamento de checkouts"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.Cog.listener("on_button_click")
    async def on_close_cart_button(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Formato: "close_cart:<cart_id>"
        if custom_id.startswith("close_cart:"):
            cart_id = custom_id.split(":", 1)[1]
            
            # Verificar se é admin
            cargos_data = db.get_document("cargos")
            cargo_admin_id = cargos_data.get("cargo_admin")
            
            is_admin = inter.author.guild_permissions.administrator
            has_admin_role = False
            if cargo_admin_id:
                has_admin_role = any(role.id == int(cargo_admin_id) for role in inter.author.roles)
            
            if not (is_admin or has_admin_role):
                await inter.response.send_message(
                    f"{emoji.wrong} Você não tem permissão para encerrar este atendimento!",
                    ephemeral=True
                )
                return
            
            # Buscar carrinho
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            # Confirmar encerramento
            await inter.response.send_message(
                f"{(getattr(emoji, 'loading', None) or '⏳')} Encerrando atendimento...",
                ephemeral=True
            )
            
            try:
                # Cancelar pagamento na Sync Pay API se aplicável e ainda não aprovado
                if cart.get("status") not in ["approved", "cancelled"]:
                    payment_data = cart.get("payment_data", {})
                    
                    # Tentar nova estrutura primeiro
                    provider_data = payment_data.get("provider", {})
                    payment_provider = provider_data.get("name")
                    
                    # Fallback para estrutura antiga
                    if not payment_provider:
                        payment_provider = payment_data.get("payment_provider")
                    
                    if payment_provider == "sync_wallet":
                        try:
                            from functions.payments.sync_wallet import cancel_sync_payment_from_settings
                            
                            # Tentar obter payment_id da nova estrutura
                            payment_id = provider_data.get("payment_id") or provider_data.get("correlation_id")
                            
                            # Fallback para estrutura antiga
                            if not payment_id:
                                raw_data = payment_data.get("raw", {}) or provider_data.get("raw_response", {})
                                payment_id = (
                                    raw_data.get("paymentId") or 
                                    raw_data.get("payment_id") or 
                                    raw_data.get("id") or
                                    payment_data.get("payment_id")
                                )
                            
                            if payment_id:
                                # Cancelar na Sync Pay API
                                result = await cancel_sync_payment_from_settings(payment_id)
                                print(f"✅ Pagamento Carteira Integrada {payment_id} cancelado ao encerrar: {result}")
                            else:
                                print(f"⚠️ Payment ID não encontrado para cancelamento Carteira Integrada")
                                
                        except Exception as e:
                            # Não falhar o encerramento se houver erro ao cancelar na API
                            print(f"❌ Erro ao cancelar pagamento Carteira Integrada: {e}")
                
                thread = inter.channel
                user_id = cart.get("user_id")
                
                # Buscar usuário
                user = await self.bot.fetch_user(user_id)
                
                # Enviar notificação para o usuário (seguindo o modo)
                if user:
                    try:
                        mode = db.get_document("custom_mode").get("mode", "embed")
                        
                        if mode == "embed":
                            embed = disnake.Embed(
                                title=f"Atendimento Encerrado",
                                description=(
                                    f"Seu atendimento foi encerrado por {inter.author.mention}.\n\n"
                                    f"Obrigado pela preferência!"
                                ),
                                color=disnake.Color.green()
                            )
                            await user.send(embed=embed)
                        else:
                            # Modo Container
                            color_data = db.get_document("custom_colors") or {}
                            primary_color = color_data.get("primary")
                            container_kwargs = {}
                            if primary_color:
                                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color.replace("#", ""), 16))
                            
                            await user.send(
                                components=[
                                    disnake.ui.Container(
                                        disnake.ui.TextDisplay(f"# {emoji.cart}\n-# Atendimento Encerrado"),
                                        disnake.ui.Separator(),
                                        disnake.ui.TextDisplay(
                                            f"Seu atendimento foi encerrado por {inter.author.mention}.\n\n"
                                            f"Obrigado pela preferência!"
                                        ),
                                        **container_kwargs
                                    )
                                ],
                                flags=disnake.MessageFlags(is_components_v2=True)
                            )
                    except Exception as e:
                        pass
                
                # Mensagem administrativa
                await inter.edit_original_message(
                    content=f"{emoji.correct} Atendimento encerrado! O tópico será deletado em breve.",
                    embed=None,
                    components=[]
                )
                
                # Mensagem no thread
                if isinstance(thread, disnake.Thread):
                    await thread.send(
                        f"{emoji.correct} Atendimento encerrado por {inter.author.mention}."
                    )
                    
                    # Gerar e enviar transcript se habilitado (antes de deletar)
                    try:
                        from modules.loja.preferences.generate_transcript import generate_cart_transcript, send_cart_transcript_to_channel
                        prefs = db.get_document("loja_preferences") or {}
                        if prefs.get("transcript_enabled", False):
                            transcript_channel_id = prefs.get("transcript_channel_id")
                            if transcript_channel_id:
                                transcript_file = await generate_cart_transcript(thread, self.bot, cart)
                                if transcript_file:
                                    await send_cart_transcript_to_channel(self.bot, transcript_file, int(transcript_channel_id), cart)
                    except Exception as e:
                        print(f"Erro ao gerar transcript: {e}")
                    
                    # Aguardar e deletar
                    import asyncio
                    await asyncio.sleep(5)
                    try:
                        await thread.delete()
                    except disnake.errors.NotFound:
                        # Thread já foi deletada, não fazer nada
                        pass
                    except Exception as delete_error:
                        # Outro erro ao deletar, logar mas não quebrar
                        print(f"Erro ao deletar thread {thread.id}: {delete_error}")
                
                # Remover do database
                if cart_id in loja_data.get("carts", {}):
                    del loja_data["carts"][cart_id]
                    db.save_document("loja_data", loja_data)
                    
            except disnake.errors.NotFound:
                # Thread ou mensagem não encontrada - pode ter sido deletada manualmente
                # Tentar enviar mensagem apenas se ainda existir
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            content=f"{emoji.correct} Atendimento encerrado!",
                            ephemeral=True
                        )
                    else:
                        try:
                            await inter.edit_original_message(
                                content=f"{emoji.correct} Atendimento encerrado!",
                                embed=None,
                                components=[]
                            )
                        except disnake.errors.NotFound:
                            # Mensagem original não existe mais, não fazer nada
                            pass
                except Exception:
                    # Se não conseguir enviar/editar, não fazer nada
                    pass
            except Exception as e:
                # Outros erros - tentar editar mensagem apenas se ainda existir
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            content=f"{emoji.wrong} Erro ao encerrar atendimento: {e}",
                            ephemeral=True
                        )
                    else:
                        try:
                            await inter.edit_original_message(
                                content=f"{emoji.wrong} Erro ao encerrar atendimento: {e}",
                                embed=None,
                                components=[]
                            )
                        except disnake.errors.NotFound:
                            # Mensagem original não existe mais, não fazer nada
                            pass
                except Exception:
                    # Se não conseguir enviar/editar, não fazer nada
                    pass
    
    @commands.Cog.listener("on_button_click")
    async def on_cancel_button(self, inter: disnake.MessageInteraction):
        """Cancela o carrinho/pagamento com resposta rápida e sem editar a mensagem errada."""
        custom_id = str(getattr(getattr(inter, "component", None), "custom_id", "") or "")
        if not custom_id.startswith("cancel_checkout:"):
            return

        thread_id = str(custom_id.split(":", 1)[1])
        loja_data = db.get_document("loja_data") or {}
        carts = loja_data.get("carts") or {}
        cart_key, cart = _find_cart_by_thread(carts, thread_id)
        if not cart:
            await inter.response.send_message(f"{emoji.wrong} Carrinho não encontrado.", ephemeral=True)
            return

        member = inter.author
        is_owner = int(getattr(member, "id", 0)) == int(cart.get("user_id", 0))
        permissions = getattr(member, "guild_permissions", None)
        is_admin = bool(getattr(permissions, "administrator", False))
        if not (is_owner or is_admin):
            await inter.response.send_message(
                f"{emoji.wrong} Você não tem permissão para cancelar este pagamento.",
                ephemeral=True,
            )
            return

        status = str(cart.get("status") or "").lower()
        if status == "approved":
            await inter.response.send_message(
                f"{emoji.wrong} Este pagamento já foi aprovado e não pode mais ser cancelado.",
                ephemeral=True,
            )
            return
        if status in {"cancelled", "canceled", "cancelado"}:
            await inter.response.send_message(
                f"{emoji.correct} Este pagamento já foi cancelado.", ephemeral=True
            )
            return

        await inter.response.defer(ephemeral=True)

        payment_data = cart.get("payment_data") or {}
        provider_data = payment_data.get("provider") or {}
        payment_provider = provider_data.get("name") or payment_data.get("payment_provider")
        provider_cancelled = False
        provider_warning = None

        if payment_provider == "sync_wallet":
            try:
                from functions.payments.sync_wallet import cancel_sync_payment_from_settings

                raw_data = payment_data.get("raw") or provider_data.get("raw_response") or {}
                payment_id = (
                    provider_data.get("payment_id")
                    or provider_data.get("correlation_id")
                    or raw_data.get("paymentId")
                    or raw_data.get("payment_id")
                    or raw_data.get("id")
                    or payment_data.get("payment_id")
                )
                if payment_id:
                    await cancel_sync_payment_from_settings(payment_id)
                    provider_cancelled = True
            except Exception as exc:
                provider_warning = str(exc)[:180]
                print(f"[CANCEL] Falha ao cancelar cobrança no provedor: {exc}")

        now = int(datetime.utcnow().timestamp())
        cart["status"] = "cancelled"
        cart["cancelled_at"] = now
        cart["cancelled_by"] = int(getattr(member, "id", 0))
        cart["updated_at"] = now
        carts[cart_key] = cart
        loja_data["carts"] = carts
        db.save_document("loja_data", loja_data)

        # Desativa os botões da mensagem de pagamento imediatamente.
        try:
            if inter.message:
                await inter.message.edit(components=[])
        except Exception:
            pass

        thread = inter.channel if isinstance(inter.channel, disnake.Thread) else None
        if thread is not None:
            try:
                await thread.send(
                    f"{emoji.wrong} Pagamento cancelado por {member.mention}. "
                    "Este atendimento será encerrado em instantes."
                )
            except Exception:
                pass

            try:
                from modules.loja.preferences.generate_transcript import (
                    generate_cart_transcript,
                    send_cart_transcript_to_channel,
                )

                prefs = db.get_document("loja_preferences") or {}
                transcript_channel_id = prefs.get("transcript_channel_id")
                if prefs.get("transcript_enabled", False) and transcript_channel_id:
                    transcript_file = await generate_cart_transcript(thread, self.bot, cart)
                    if transcript_file:
                        await send_cart_transcript_to_channel(
                            self.bot, transcript_file, int(transcript_channel_id), cart
                        )
            except Exception as exc:
                print(f"[CANCEL] Erro ao gerar transcript: {exc}")

        suffix = ""
        if provider_cancelled:
            suffix = " A cobrança também foi cancelada no provedor."
        elif provider_warning:
            suffix = " O carrinho foi cancelado; a baixa no provedor não pôde ser confirmada."
        await inter.followup.send(
            f"{emoji.correct} Pagamento cancelado com sucesso.{suffix}", ephemeral=True
        )

        if thread is not None:
            await asyncio.sleep(5)
            try:
                await thread.delete(reason=f"Pagamento cancelado por {member} ({member.id})")
            except disnake.NotFound:
                pass
            except Exception as exc:
                print(f"[CANCEL] Não foi possível excluir a thread {thread.id}: {exc}")

    @commands.Cog.listener("on_button_click")
    async def on_copy_pix_button(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Formato: "copy_pix:<thread_id>"
        if custom_id.startswith("copy_pix:"):
            thread_id = custom_id.split(":", 1)[1]
            
            # Buscar código PIX
            loja_data = db.get_document("loja_data") or {}
            _cart_key, cart = _find_cart_by_thread(loja_data.get("carts") or {}, thread_id)
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            member = inter.author
            is_owner = int(getattr(member, "id", 0)) == int(cart.get("user_id", 0))
            permissions = getattr(member, "guild_permissions", None)
            is_admin = bool(getattr(permissions, "administrator", False))
            if not (is_owner or is_admin):
                await inter.response.send_message(
                    f"{emoji.wrong} Apenas o comprador pode copiar este código PIX.",
                    ephemeral=True,
                )
                return

            payment_data = cart.get("payment_data", {})
            
            # Tentar nova estrutura primeiro
            local_data = payment_data.get("local", {})
            copy_code = local_data.get("copy_code")
            
            # Fallback para estrutura antiga
            if not copy_code:
                copy_code = payment_data.get("copy_code")
            
            # Fallback para raw data
            if not copy_code:
                raw_data = payment_data.get("raw", {}) or payment_data.get("provider", {}).get("raw_response", {})
                copy_code = raw_data.get("pix_copia_cola") or raw_data.get("copy_paste") or raw_data.get("emv") or raw_data.get("qrCode")
            
            if not copy_code:
                await inter.response.send_message(
                    f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Código PIX não disponível!",
                    ephemeral=True
                )
                return
            
            # Enviar código PIX
            await inter.response.send_message(
                f"{emoji.pix} **Código PIX copia e cola**\n```\n{copy_code}\n```",
                ephemeral=True,
            )
    
    @commands.Cog.listener("on_button_click")
    async def on_approve_manual_pix_button(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Formato: "approve_manual_pix:<thread_id>"
        if custom_id.startswith("approve_manual_pix:"):
            thread_id = custom_id.split(":", 1)[1]
            
            # Verificar se tem permissão (admin ou cargo específico)
            cargos_data = db.get_document("cargos")
            cargo_admin_id = cargos_data.get("cargo_admin")
            
            is_admin = inter.author.guild_permissions.administrator
            has_admin_role = False
            if cargo_admin_id:
                has_admin_role = any(role.id == int(cargo_admin_id) for role in inter.author.roles)
            
            if not (is_admin or has_admin_role):
                await inter.response.send_message(
                    f"{emoji.wrong} Você não tem permissão para aprovar pagamentos!",
                    ephemeral=True
                )
                return
            
            # Buscar carrinho (pode estar salvo como thread_id ou como string)
            loja_data = db.get_document("loja_data")
            cart_id = str(thread_id)  # Usar thread_id como cart_id (padrão)
            cart = loja_data.get("carts", {}).get(cart_id)
            
            # Se não encontrou, tentar buscar por thread_id como int
            if not cart:
                cart = loja_data.get("carts", {}).get(thread_id)
                if cart:
                    cart_id = thread_id
            
            # Se ainda não encontrou, buscar por thread_id no valor
            if not cart:
                for cart_key, cart_value in loja_data.get("carts", {}).items():
                    if cart_value.get("thread_id") == int(thread_id):
                        cart = cart_value
                        cart_id = cart_key  # Usar o cart_id correto encontrado
                        break
            
            if not cart:
                await inter.response.send_message(
                    f"{emoji.wrong} Carrinho não encontrado!",
                    ephemeral=True
                )
                return
            
            # Verificar se já foi aprovado
            if cart.get("status") == "approved":
                await inter.response.send_message(
                    f"{emoji.wrong} Este pagamento já foi aprovado!",
                    ephemeral=True
                )
                return
            
            # Fazer defer imediatamente para evitar timeout
            await inter.response.defer(ephemeral=True)
            
            try:
                payment_data = cart.get("payment_data", {})
                
                # Tentar nova estrutura primeiro
                provider_data = payment_data.get("provider", {})
                payment_id = provider_data.get("payment_id") or provider_data.get("charge_id")
                
                # Fallback para estrutura antiga
                if not payment_id:
                    payment_id = payment_data.get("payment_id") or payment_data.get("id")
                
                if payment_id:
                    await approve_manual_pix_payment(payment_id)
                
                # Atualizar status do carrinho
                cart["status"] = "approved"
                cart["approved_at"] = int(datetime.utcnow().timestamp())
                cart["approved_by"] = inter.author.id
                cart["updated_at"] = int(datetime.utcnow().timestamp())
                loja_data["carts"][cart_id] = cart
                db.save_document("loja_data", loja_data)
                
                # Notificar no tópico
                thread = inter.channel
                
                # A renomeação da thread será feita em _handle_payment_approved
                # baseada no tipo de entrega dos produtos (✅ para automático, ⌚ para manual)
                
                # A mensagem pública de aprovação é enviada exclusivamente dentro de
                # _handle_payment_approved, depois que o status estiver confirmado.
                
                # Processar entrega automática. A confirmação pública completa é
                # gerada por _handle_payment_approved; não enviamos uma segunda
                # mensagem efêmera de sucesso para o administrador.
                from .checkout import _handle_payment_approved
                await _handle_payment_approved(cart_id, self.bot)

                # Remove a resposta diferida silenciosa para não deixar uma mensagem
                # "Pagamento aprovado..." adicional após a aprovação.
                try:
                    await inter.delete_original_response()
                except Exception:
                    pass
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Mensagem administrativa - usar followup já que fizemos defer
                await inter.followup.send(
                    content=f"{emoji.wrong} Erro ao aprovar pagamento: {e}",
                    ephemeral=True
                )


def setup(bot: commands.Bot):
    bot.add_cog(CancelCheckout(bot))
