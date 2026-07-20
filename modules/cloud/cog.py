import disnake
from disnake.ext import commands
import aiohttp
from functions.emoji import emoji
from functions.database import database as db
from functions.message import message, embed_message
from functions.interaction_runtime import respond_panel
from functions.utils import utils
from . import helpers
from . import config_credenciais
from . import config_mensagem
from . import auth_logs
from . import update_api
from .config_definicoes import DefinicoesView_components, DefinicoesView_embed
from .manage_tasks import ManageTasksView_components, ManageTasksView_embed, ManageTasksSelectView_components, TaskDetailsView_components, ManageTasksSelectView_embed, TaskDetailsView_embed
from .create_task_modal import CreateTaskModal
from . import reference_interface


class VerifiedRoleModal(disnake.ui.Modal):
    def __init__(self):
        super().__init__(
            title="Configurar Cargo de Verificado",
            custom_id="Cloud_VerifiedRoleModal",
            components=[
                disnake.ui.Label(
                    text="Cargo de Verificado",
                    description="O bot adicionará este cargo quando o membro clicar em Verificar.",
                    component=disnake.ui.RoleSelect(
                        custom_id="cloud_verified_role",
                        placeholder="Selecione o cargo que será entregue",
                        min_values=1,
                        max_values=1,
                    ),
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        from .local_verification import save_verified_role

        selected = (getattr(inter, "resolved_values", {}) or {}).get("cloud_verified_role")
        if isinstance(selected, (list, tuple)):
            selected = selected[0] if selected else None
        if isinstance(selected, (str, int)) and inter.guild:
            selected = inter.guild.get_role(int(selected))
        if not isinstance(selected, disnake.Role):
            return await inter.response.send_message(
                f"{emoji.wrong} Selecione um cargo válido.", ephemeral=True
            )
        if selected.is_default() or selected.managed:
            return await inter.response.send_message(
                f"{emoji.wrong} Esse cargo não pode ser usado para verificação.", ephemeral=True
            )
        me = inter.guild.me if inter.guild else None
        if me is None or not me.guild_permissions.manage_roles:
            return await inter.response.send_message(
                f"{emoji.wrong} O bot precisa da permissão `Gerenciar Cargos`.", ephemeral=True
            )
        if me.top_role <= selected:
            return await inter.response.send_message(
                f"{emoji.wrong} Coloque o cargo do bot acima de {selected.mention}.", ephemeral=True
            )
        save_verified_role(selected)
        await inter.response.send_message(
            f"{emoji.correct} Cargo de verificado definido como {selected.mention}.\n"
            f"{emoji.verified} A verificação local está pronta para os membros.",
            ephemeral=True,
        )

class Cloud(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        update_api.set_bot_instance(bot)
        try:
            update_api.register_websocket_callbacks()
        except Exception as e:
            print(f'[Cloud Cog] Falha ao registrar callbacks do WebSocket: {e}')

    async def _definir_preferencias(self, inter: disnake.MessageInteraction):
        await inter.response.send_message('Lógica para definir preferências a ser implementada.', ephemeral=True)

    async def _gerenciar_gift(self, inter: disnake.MessageInteraction):
        """Mostra container ou embed com opções de gerenciamento de gifts"""
        try:
            mode = db.get_document('custom_mode').get('mode')
            if mode == 'embed':
                await embed_message.wait(inter)
                primary_color_hex = db.get_document('custom_colors').get('primary')
                embed = disnake.Embed(title=f'Painel > ZYNEX Cloud > Gerenciar Gifts', description='Use os botões abaixo para gerenciar os gifts.')
                if primary_color_hex:
                    embed.color = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                components = [disnake.ui.ActionRow(disnake.ui.Button(label='Criar Gift', style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id='CloudGift_Create'), disnake.ui.Button(label='Gerenciar Gifts', style=disnake.ButtonStyle.grey, emoji=emoji.settings, custom_id='CloudGift_Manage'), disnake.ui.Button(label='Excluir Gifts', style=disnake.ButtonStyle.red, emoji=emoji.wrong, custom_id='CloudGift_Delete')), disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='Cloud_Back'))]
                await inter.edit_original_response(content=None, embed=embed, components=components)
            else:
                await message.wait(inter)
                primary_color_hex = db.get_document('custom_colors').get('primary')
                container_kwargs = {}
                if primary_color_hex:
                    container_kwargs['accent_colour'] = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Painel > ZYNEX Cloud > **Gerenciar Gifts**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.ActionRow(disnake.ui.Button(label='Criar Gift', style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id='CloudGift_Create'), disnake.ui.Button(label='Gerenciar Gifts', style=disnake.ButtonStyle.grey, emoji=emoji.settings, custom_id='CloudGift_Manage'), disnake.ui.Button(label='Excluir Gifts', style=disnake.ButtonStyle.red, emoji=emoji.wrong, custom_id='CloudGift_Delete')), **container_kwargs)
                buttons = disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='Cloud_Back'))
                await inter.edit_original_response(content=None, components=[container, buttons])
        except Exception as e:
            print(f'Erro ao mostrar gerenciamento de gifts: {e}')
            try:
                if not inter.response.is_done():
                    await inter.response.send_message('Erro ao carregar gerenciamento de gifts.', ephemeral=True)
                else:
                    await inter.edit_original_response('Erro ao carregar gerenciamento de gifts.')
            except:
                await inter.followup.send('Erro ao carregar gerenciamento de gifts.', ephemeral=True)

    async def _show_delete_options(self, inter: disnake.MessageInteraction):
        """Mostra as opções de deleção de gifts"""
        try:
            mode = db.get_document('custom_mode').get('mode')
            primary_color_hex = db.get_document('custom_colors').get('primary')
            buttons = disnake.ui.ActionRow(disnake.ui.Button(label='Excluir da Lista', style=disnake.ButtonStyle.grey, emoji=emoji.embed, custom_id='CloudGift_DeleteFromList'), disnake.ui.Button(label='Excluir por Código', style=disnake.ButtonStyle.grey, emoji=emoji.search, custom_id='CloudGift_DeleteByCode'), disnake.ui.Button(label='Excluir Todos', style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id='CloudGift_DeleteAll'))
            back_button = disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='CloudGift_Back'))
            if mode == 'embed':
                await embed_message.wait(inter)
                embed = disnake.Embed(title=f'Painel > ZYNEX Cloud > Excluir Gifts', description='Selecione um método para excluir os gifts.')
                if primary_color_hex:
                    embed.color = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                await inter.edit_original_response(content=None, embed=embed, components=[buttons, back_button])
            else:
                await message.wait(inter)
                container_kwargs = {}
                if primary_color_hex:
                    container_kwargs['accent_colour'] = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Painel > ZYNEX Cloud > **Excluir Gifts**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('Selecione um método para excluir os gifts.'), buttons, **container_kwargs)
                await inter.edit_original_response(content=None, components=[container, back_button])
        except Exception as e:
            print(f'Erro ao mostrar opções de deleção de gifts: {e}')
            try:
                if not inter.response.is_done():
                    await inter.response.send_message('Erro ao carregar opções de deleção.', ephemeral=True)
                else:
                    await inter.edit_original_response('Erro ao carregar opções de deleção.')
            except:
                await inter.followup.send('Erro ao carregar opções de deleção.', ephemeral=True)

    async def _create_gift_modal(self, inter: disnake.MessageInteraction):
        """Mostra modal para criar gift"""
        try:
            from .create_gift_modal import CreateGiftModal
            modal = CreateGiftModal(self.bot)
            await inter.response.send_modal(modal)
        except Exception as e:
            print(f'Erro ao mostrar modal de criar gift: {e}')
            await inter.response.send_message('Erro ao carregar modal de criar gift.', ephemeral=True)

    async def _manage_gifts_select(self, inter: disnake.MessageInteraction):
        """Mostra select menu para gerenciar gifts"""
        try:
            mode = db.get_document('custom_mode').get('mode')
            if mode == 'embed':
                await embed_message.wait(inter)
            else:
                await message.wait(inter)
            await self._load_gifts_for_manage(inter)
        except Exception as e:
            print(f'Erro ao mostrar select de gerenciar gifts: {e}')
            try:
                if not inter.response.is_done():
                    await inter.response.send_message('Erro ao carregar gerenciamento de gifts.', ephemeral=True)
                else:
                    await inter.edit_original_response('Erro ao carregar gerenciamento de gifts.')
            except:
                await inter.followup.send('Erro ao carregar gerenciamento de gifts.', ephemeral=True)

    async def _handle_manage_gift_select(self, inter: disnake.MessageInteraction):
        """Handler para seleção de gift para gerenciar"""
        try:
            selected_value = inter.values[0]
            await self._manage_gift_modal(inter, selected_value)
        except disnake.errors.HTTPException as e:
            if 'already been acknowledged' in str(e):
                try:
                    await inter.followup.send('Por favor, selecione novamente.', ephemeral=True)
                except:
                    pass
            else:
                print(f'Erro ao processar seleção de gift para gerenciar: {e}')
                try:
                    await inter.followup.send('Erro ao processar seleção.', ephemeral=True)
                except:
                    pass
        except Exception as e:
            print(f'Erro ao processar seleção de gift para gerenciar: {e}')
            try:
                if not inter.response.is_done():
                    await inter.response.send_message('Erro ao processar seleção.', ephemeral=True)
                else:
                    await inter.followup.send('Erro ao processar seleção.', ephemeral=True)
            except:
                pass

    async def _handle_delete_gift_select(self, inter: disnake.MessageInteraction):
        """Handler para seleção de gift para deletar"""
        try:
            selected_value = inter.values[0]
            await self._delete_gift_modal(inter, selected_value)
        except disnake.errors.HTTPException as e:
            if 'already been acknowledged' in str(e):
                try:
                    await inter.followup.send('Por favor, selecione novamente.', ephemeral=True)
                except:
                    pass
            else:
                print(f'Erro ao processar seleção de gift para deletar: {e}')
                try:
                    await inter.followup.send('Erro ao processar seleção.', ephemeral=True)
                except:
                    pass
        except Exception as e:
            print(f'Erro ao processar seleção de gift para deletar: {e}')
            try:
                if not inter.response.is_done():
                    await inter.response.send_message('Erro ao processar seleção.', ephemeral=True)
                else:
                    await inter.followup.send('Erro ao processar seleção.', ephemeral=True)
            except:
                pass

    async def _load_gifts_for_manage(self, inter: disnake.MessageInteraction):
        """Carrega gifts para gerenciar"""
        try:
            mode = db.get_document('custom_mode').get('mode')
            primary_color_hex = db.get_document('custom_colors').get('primary')
            cloud_config = db.get_document('cloud_data') or {}
            bot_id = cloud_config.get('client_id')
            if not bot_id:
                if mode == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description='Bot não configurado.', color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('Bot não configurado.'))
                    await inter.edit_original_response(components=[container])
                return
            from .update_api import get_websocket_manager
            ws_manager = get_websocket_manager()
            if not ws_manager.is_connected():
                if mode == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description='WebSocket não conectado.', color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('WebSocket não conectado.'))
                    await inter.edit_original_response(components=[container])
                return
            response = await ws_manager.get_gifts(bot_id)
            if not response.get('success'):
                error_message = f"Erro ao carregar gifts: {response.get('message', 'Erro desconhecido')}"
                if mode == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description=error_message, color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay(error_message))
                    await inter.edit_original_response(components=[container])
                return
            gifts = response.get('data', {}).get('gifts', [])
            if not gifts:
                back_button = disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='CloudGift_Back')
                if mode == 'embed':
                    embed = disnake.Embed(title=f'Painel > ZYNEX Cloud > Gerenciamento de Gifts', description='Nenhum gift encontrado para este bot.')
                    if primary_color_hex:
                        embed.color = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                    await inter.edit_original_response(embed=embed, components=[disnake.ui.ActionRow(back_button)])
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Painel > ZYNEX Cloud > **Gerenciamento de Gifts**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('Nenhum gift encontrado para este bot.'))
                    await inter.edit_original_response(components=[container, disnake.ui.ActionRow(back_button)])
                return
            gifts_to_display = gifts[:125]
            gift_chunks = [gifts_to_display[i:i + 25] for i in range(0, len(gifts_to_display), 25)]
            selects_components = []
            for i, chunk in enumerate(gift_chunks):
                select = disnake.ui.StringSelect(placeholder=f'Selecione um gift para gerenciar ({i * 25 + 1}-{i * 25 + len(chunk)})...', custom_id=f'manage_gift_select_{i}', min_values=1, max_values=1)
                for gift in chunk:
                    status_emoji = '✅' if gift.get('status') == 'active' else '❌'
                    select.add_option(label=f"{status_emoji} {gift.get('id', 'Unknown')[:8]}...", value=gift.get('id'), description=f"{gift.get('members_count', 0)} membros - {gift.get('status', 'unknown')}")
                selects_components.append(disnake.ui.ActionRow(select))
            back_button = disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='CloudGift_Back')
            if mode == 'embed':
                embed = disnake.Embed(title=f'Painel > ZYNEX Cloud > Gerenciamento de Gifts', description='Selecione um gift da lista abaixo para gerenciar.')
                if primary_color_hex:
                    embed.color = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                components = selects_components + [disnake.ui.ActionRow(back_button)]
                await inter.edit_original_response(embed=embed, components=components)
            else:
                container_kwargs = {}
                if primary_color_hex:
                    container_kwargs['accent_colour'] = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                container_children = [disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Painel > ZYNEX Cloud > **Gerenciamento de Gifts**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small)]
                container_children.extend(selects_components)
                container = disnake.ui.Container(*container_children, **container_kwargs)
                await inter.edit_original_response(components=[container, disnake.ui.ActionRow(back_button)])
        except Exception as e:
            print(f'Erro ao carregar gifts para gerenciar: {e}')
            try:
                error_message = f'Erro ao carregar gifts: {str(e)}'
                if db.get_document('custom_mode').get('mode') == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description=error_message, color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay(error_message))
                    await inter.edit_original_response(components=[container])
            except:
                await inter.followup.send(f'{emoji.wrong} Erro ao carregar gifts: {str(e)}', ephemeral=True)

    async def _delete_gifts_select(self, inter: disnake.MessageInteraction):
        """Mostra select menu para deletar gifts"""
        try:
            mode = db.get_document('custom_mode').get('mode')
            if mode == 'embed':
                await embed_message.wait(inter)
            else:
                await message.wait(inter)
            await self._load_gifts_for_delete(inter)
        except Exception as e:
            print(f'Erro ao mostrar select de deletar gifts: {e}')
            try:
                if not inter.response.is_done():
                    await inter.response.send_message('Erro ao carregar seleção de gifts para deletar.', ephemeral=True)
                else:
                    await inter.edit_original_response('Erro ao carregar seleção de gifts para deletar.')
            except:
                await inter.followup.send('Erro ao carregar seleção de gifts para deletar.', ephemeral=True)

    async def _load_gifts_for_delete(self, inter: disnake.MessageInteraction):
        """Carrega gifts para deletar"""
        try:
            mode = db.get_document('custom_mode').get('mode')
            primary_color_hex = db.get_document('custom_colors').get('primary')
            cloud_config = db.get_document('cloud_data') or {}
            bot_id = cloud_config.get('client_id')
            if not bot_id:
                if mode == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description='Bot não configurado.', color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('Bot não configurado.'))
                    await inter.edit_original_response(components=[container])
                return
            from .update_api import get_websocket_manager
            ws_manager = get_websocket_manager()
            if not ws_manager.is_connected():
                if mode == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description='WebSocket não conectado.', color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('WebSocket não conectado.'))
                    await inter.edit_original_response(components=[container])
                return
            response = await ws_manager.get_gifts(bot_id)
            if not response.get('success'):
                error_message = f"Erro ao carregar gifts: {response.get('message', 'Erro desconhecido')}"
                if mode == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description=error_message, color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay(error_message))
                    await inter.edit_original_response(components=[container])
                return
            gifts = response.get('data', {}).get('gifts', [])
            if not gifts:
                back_button = disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='CloudGift_Back')
                if mode == 'embed':
                    embed = disnake.Embed(title=f'Painel > ZYNEX Cloud > Deletar Gifts', description='Nenhum gift encontrado para este bot.')
                    if primary_color_hex:
                        embed.color = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                    await inter.edit_original_response(embed=embed, components=[disnake.ui.ActionRow(back_button)])
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Painel > ZYNEX Cloud > **Deletar Gifts**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('Nenhum gift encontrado para este bot.'))
                    await inter.edit_original_response(components=[container, disnake.ui.ActionRow(back_button)])
                return
            gifts_to_display = gifts[:125]
            gift_chunks = [gifts_to_display[i:i + 25] for i in range(0, len(gifts_to_display), 25)]
            selects_components = []
            for i, chunk in enumerate(gift_chunks):
                select = disnake.ui.StringSelect(placeholder=f'Selecione um gift para deletar ({i * 25 + 1}-{i * 25 + len(chunk)})...', custom_id=f'delete_gift_select_{i}', min_values=1, max_values=1)
                for gift in chunk:
                    status_emoji = '✅' if gift.get('status') == 'active' else '❌'
                    select.add_option(label=f"{status_emoji} {gift.get('id', 'Unknown')[:8]}...", value=gift.get('id'), description=f"{gift.get('members_count', 0)} membros - {gift.get('status', 'unknown')}")
                selects_components.append(disnake.ui.ActionRow(select))
            back_button = disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='CloudGift_Back')
            if mode == 'embed':
                embed = disnake.Embed(title=f'Painel > ZYNEX Cloud > Deletar Gifts', description='Selecione um gift da lista abaixo para deletar.')
                if primary_color_hex:
                    embed.color = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                components = selects_components + [disnake.ui.ActionRow(back_button)]
                await inter.edit_original_response(embed=embed, components=components)
            else:
                container_kwargs = {}
                if primary_color_hex:
                    container_kwargs['accent_colour'] = disnake.Colour(int(primary_color_hex.replace('#', ''), 16))
                container_children = [disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Painel > ZYNEX Cloud > **Deletar Gifts**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small)]
                container_children.extend(selects_components)
                container = disnake.ui.Container(*container_children, **container_kwargs)
                await inter.edit_original_response(components=[container, disnake.ui.ActionRow(back_button)])
        except Exception as e:
            print(f'Erro ao carregar gifts para deletar: {e}')
            try:
                error_message = f'Erro ao carregar gifts: {str(e)}'
                if db.get_document('custom_mode').get('mode') == 'embed':
                    embed = disnake.Embed(title=f'{emoji.wrong} Erro', description=error_message, color=disnake.Color.red())
                    await inter.edit_original_response(embed=embed)
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay(error_message))
                    await inter.edit_original_response(components=[container])
            except:
                await inter.followup.send(f'{emoji.wrong} Erro ao carregar gifts: {str(e)}', ephemeral=True)

    async def _manage_gift_modal(self, inter: disnake.MessageInteraction, gift_id: str):
        """Mostra modal para editar gift"""
        try:
            from .edit_gift_modal import EditGiftModal
            modal = EditGiftModal(self.bot, gift_id)
            await inter.response.send_modal(modal)
        except Exception as e:
            print(f'Erro ao mostrar modal de editar gift: {e}')
            await inter.response.send_message('Erro ao abrir modal de edição.', ephemeral=True)

    async def _delete_gift_modal(self, inter: disnake.MessageInteraction, gift_id: str):
        """Mostra modal para confirmar deleção de gift"""
        try:
            from .delete_gift_modal import DeleteGiftModal
            modal = DeleteGiftModal(self.bot, gift_id)
            await inter.response.send_modal(modal)
        except Exception as e:
            print(f'Erro ao mostrar modal de deletar gift: {e}')
            await inter.response.send_message('Erro ao abrir modal de confirmação.', ephemeral=True)

    async def process_log_channel(self, inter: disnake.ModalInteraction, channel_id_str: str):
        try:
            channel_id = int(channel_id_str)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                if not inter.response.is_done():
                    await inter.response.send_message(f'{emoji.wrong} Canal não encontrado. ID: {channel_id}\n\n**Verifique se:**\n• O canal existe\n• O bot tem acesso ao canal\n• O ID está correto', ephemeral=True)
                return
            if not isinstance(channel, disnake.TextChannel):
                if not inter.response.is_done():
                    await inter.response.send_message(f'{emoji.wrong} O canal encontrado não é um canal de texto. Tipo: {type(channel).__name__}', ephemeral=True)
                return
        except (ValueError, TypeError):
            if not inter.response.is_done():
                await inter.response.send_message(f'{emoji.wrong} ID do canal inválido. Use apenas números.', ephemeral=True)
            return
        cloud_config = db.get_document('cloud_data') or {}
        cloud_config['log_channel_id'] = channel_id
        db.save_document('cloud_data', cloud_config)
        await self.display_cloud_panel(inter)

    def CloudComponents(self, inter: disnake.MessageInteraction, status_text: str = "") -> list[disnake.ui.Container]:
        return reference_interface.components(inter, self.bot)

    def CloudEmbed(self, inter: disnake.Interaction, status_text: str = ""):
        return reference_interface.embed(inter, self.bot)

    async def display_cloud_panel(self, inter):
        mode = (db.get_document('custom_mode') or {}).get('mode', 'components')
        if mode == 'embed':
            embed, components = self.CloudEmbed(inter)
            panel = {"embed": embed, "components": components}
        else:
            panel = {"components": self.CloudComponents(inter)}
        return await respond_panel(inter, panel, prefer_edit=True)

    @commands.Cog.listener('on_message_interaction')
    async def on_message_interaction(self, inter: disnake.MessageInteraction):
        return None

    @commands.Cog.listener('on_button_click')
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id.startswith('Cloud'):
            return
        needs_defer = inter.component.custom_id not in ['CloudTasks_Create', 'Cloud_SetCredentialsModal', 'Cloud_SetVerifiedRole', 'Cloud_GetAuthLink', 'Cloud_DefinirLogs', 'CloudGift_Create', 'CloudGift_DeleteByCode', 'CloudGift_DeleteAll', 'CloudMsgEdit_EditButton', 'CloudMsgEdit_EditContent', 'CloudSend_External']
        if needs_defer and (not inter.response.is_done()):
            try:
                await inter.response.defer()
            except disnake.errors.InteractionResponded:
                pass
        match inter.component.custom_id:
            case 'Cloud_ToggleSystem':
                cloud_conf = db.get_document('cloud_data') or {}
                new_state = not bool(cloud_conf.get('oauth_enabled', False))
                if new_state and not cloud_conf.get('client_id'):
                    # Abrir a configuração em vez de deixar o clique sem resposta.
                    return await config_credenciais.show_panel(inter)
                cloud_conf['oauth_enabled'] = new_state
                cloud_conf['verification_mode'] = 'oauth' if new_state else cloud_conf.get('verification_mode', 'local')
                db.save_document('cloud_data', cloud_conf)
                return await self.display_cloud_panel(inter)
            case 'Cloud_RecoverMembers':
                cloud_conf = db.get_document('cloud_data') or {}
                client_id = cloud_conf.get('client_id')
                if not client_id:
                    return await inter.followup.send(f"{emoji.wrong} Configure as credenciais OAuth2 primeiro.", ephemeral=True)
                try:
                    from .update_api import get_websocket_manager
                    manager = get_websocket_manager()
                    if not manager.is_connected():
                        return await inter.followup.send(f"{emoji.warn} ZenyxClous está offline. Tente novamente após a conexão ser restabelecida.", ephemeral=True)
                    response = await manager.recover_members(str(client_id), str(inter.guild.id) if inter.guild else None)
                    if response.get('success'):
                        data = response.get('data') or {}
                        recovered = int(data.get('recovered', data.get('count', 0)) or 0)
                        cloud_conf['oauth_member_count'] = max(int(cloud_conf.get('oauth_member_count', 0) or 0), recovered)
                        db.save_document('cloud_data', cloud_conf)
                        await inter.followup.send(f"{emoji.correct} Recuperação solicitada. Membros processados: `{recovered}`.", ephemeral=True)
                    else:
                        await inter.followup.send(f"{emoji.wrong} {response.get('message', 'Não foi possível recuperar os membros.')}", ephemeral=True)
                except Exception as exc:
                    await inter.followup.send(f"{emoji.wrong} Falha ao recuperar membros: `{type(exc).__name__}`.", ephemeral=True)
                return
            case 'Cloud_UnlinkOAuth':
                cloud_conf = db.get_document('cloud_data') or {}
                for key in ('client_id', 'client_secret', 'token', 'bot_id', 'oauth_member_count'):
                    cloud_conf.pop(key, None)
                cloud_conf['oauth_enabled'] = False
                cloud_conf['verification_mode'] = 'local'
                db.save_document('cloud_data', cloud_conf)
                await inter.followup.send(f"{emoji.correct} Aplicação OAuth2 desvinculada.", ephemeral=True)
                return await self.display_cloud_panel(inter)
            case 'Cloud_ManageTasks':
                cloud_conf = db.get_document('cloud_data') or {}
                if not bool(cloud_conf.get('client_id')):
                    if inter.response.is_done():
                        await inter.followup.send(f"{emoji.off} ZYNEX Cloud não está configurado. Use 'Editar Credenciais' primeiro.", ephemeral=True)
                    else:
                        await inter.response.send_message(f"{emoji.off} ZYNEX Cloud não está configurado. Use 'Editar Credenciais' primeiro.", ephemeral=True)
                    return
                mode = db.get_document('custom_mode').get('mode')
                if mode == 'embed':
                    await embed_message.wait(inter)
                    embed, components = ManageTasksView_embed(inter)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                else:
                    await message.wait(inter)
                    components = await ManageTasksView_components(inter)
                    await inter.edit_original_message(content=None, components=components)
            case 'CloudTasks_Create':
                await inter.response.send_modal(CreateTaskModal(self.bot))
            case 'CloudTasks_Manage':
                mode = db.get_document('custom_mode').get('mode')
                if mode == 'embed':
                    await embed_message.wait(inter)
                    embed, components = ManageTasksSelectView_embed(inter)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                else:
                    await message.wait(inter)
                    components = ManageTasksSelectView_components(inter)
                    await inter.edit_original_message(content=None, components=components)
            case 'CloudTasks_Back':
                mode = db.get_document('custom_mode').get('mode')
                if mode == 'embed':
                    await embed_message.wait(inter)
                    embed, components = ManageTasksView_embed(inter)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                else:
                    await message.wait(inter)
                    components = await ManageTasksView_components(inter)
                    await inter.edit_original_message(components=components)
            case 'Cloud_SetVerifiedRole':
                await inter.response.send_modal(VerifiedRoleModal())
            case 'Cloud_ToggleVerificationMode':
                cloud_conf = db.get_document('cloud_data') or {}
                current = str(cloud_conf.get('verification_mode') or 'local').lower()
                new_mode = 'oauth' if current == 'local' else 'local'
                if new_mode == 'oauth' and not cloud_conf.get('client_id'):
                    if inter.response.is_done():
                        await inter.followup.send(f"{emoji.wrong} Configure as credenciais OAuth2 antes de ativar esse modo.", ephemeral=True)
                    else:
                        await inter.response.send_message(f"{emoji.wrong} Configure as credenciais OAuth2 antes de ativar esse modo.", ephemeral=True)
                    return
                cloud_conf['verification_mode'] = new_mode
                db.save_document('cloud_data', cloud_conf)
                await self.display_cloud_panel(inter)
            case 'Cloud_ConfigurarCredenciais':
                await config_credenciais.show_panel(inter)
            case 'Cloud_CopyAuthURL':
                from .cloud_config import get_auth_callback_url
                auth_url = get_auth_callback_url()
                if inter.response.is_done():
                    await inter.followup.send(f'{auth_url}', ephemeral=True)
                else:
                    await inter.response.send_message(f'{auth_url}', ephemeral=True)
            case 'Cloud_SetCredentialsModal':
                cloud_config = db.get_document('cloud_data') or {}
                bot_token = cloud_config.get('token', '')
                client_secret = cloud_config.get('client_secret', '')
                await inter.response.send_modal(config_credenciais.CredentialModal(self.bot, bot_token=bot_token, client_secret=client_secret))
            case 'Cloud_MainPanel':
                await self.display_cloud_panel(inter)
            case 'Cloud_Back':
                await self.display_cloud_panel(inter)
            case 'Cloud_Definicoes':
                mode = db.get_document('custom_mode').get('mode')
                if mode == 'embed':
                    await embed_message.wait(inter)
                    embed, components = DefinicoesView_embed(inter)
                    await inter.edit_original_message(embed=embed, components=components)
                else:
                    await message.wait(inter)
                    components = DefinicoesView_components(inter)
                    await inter.edit_original_message(components=components)
            case 'Cloud_Preferencias':
                cloud_conf = db.get_document('cloud_data') or {}
                if not bool(cloud_conf.get('client_id')):
                    if inter.response.is_done():
                        await inter.followup.send(f"{emoji.off} SyncCloud não está configurado. Use 'Editar Credenciais' primeiro.", ephemeral=True)
                    else:
                        await inter.response.send_message(f"{emoji.off} SyncCloud não está configurado. Use 'Editar Credenciais' primeiro.", ephemeral=True)
                    return
                await self._definir_preferencias(inter)
            case 'Cloud_DefinirMensagens':
                cloud_conf = db.get_document('cloud_data') or {}
                mode = str(cloud_conf.get('verification_mode') or 'local').lower()
                has_role = bool((db.get_document('cargos') or {}).get('cargo_verificado'))
                ready = bool(cloud_conf.get('client_id')) if mode == 'oauth' else has_role
                if not ready:
                    content = f"{emoji.off} Configure o cargo de verificado antes de editar e publicar a mensagem."
                    if inter.response.is_done():
                        await inter.followup.send(content, ephemeral=True)
                    else:
                        await inter.response.send_message(content, ephemeral=True)
                    return
                await config_mensagem.show_panel(inter)
            case 'Cloud_DefinirLogs':
                cloud_config = db.get_document('cloud_data') or {}
                current_log_channel_id = str(cloud_config.get('log_channel_id', ''))
                modal = helpers.LogChannelModal(self.bot, current_channel_id=current_log_channel_id)
                await inter.response.send_modal(modal)
            case 'Cloud_GerenciarGift':
                cloud_conf = db.get_document('cloud_data') or {}
                if not bool(cloud_conf.get('client_id')):
                    if inter.response.is_done():
                        await inter.followup.send(f"{emoji.off} SyncCloud não está configurado. Use 'Editar Credenciais' primeiro.", ephemeral=True)
                    else:
                        await inter.response.send_message(f"{emoji.off} SyncCloud não está configurado. Use 'Editar Credenciais' primeiro.", ephemeral=True)
                    return
                await self._gerenciar_gift(inter)
            case 'CloudGift_Create':
                await self._create_gift_modal(inter)
            case 'CloudGift_Manage':
                await self._manage_gifts_select(inter)
            case 'CloudGift_Delete':
                await self._show_delete_options(inter)
            case 'CloudGift_DeleteFromList':
                await self._delete_gifts_select(inter)
            case 'CloudGift_DeleteByCode':
                from .delete_gift_modal import DeleteGiftByCodeModal
                await inter.response.send_modal(DeleteGiftByCodeModal(self.bot))
            case 'CloudGift_DeleteAll':
                from .delete_gift_modal import DeleteAllGiftsModal
                await inter.response.send_modal(DeleteAllGiftsModal(self.bot))
            case 'CloudGift_Back':
                await self._gerenciar_gift(inter)
            case 'Cloud_GetAuthLink':
                from .local_verification import get_verification_mode, verify_member
                from .verification_check import get_verification_message_and_view

                if not isinstance(inter.user, disnake.Member):
                    return await inter.response.send_message(
                        f'{emoji.wrong} Use este botão dentro do servidor.', ephemeral=True
                    )

                if get_verification_mode() == 'oauth':
                    message_text, view = get_verification_message_and_view(inter)
                    if not message_text or view is None:
                        return await inter.response.send_message(
                            f'{emoji.wrong} O OAuth2 externo ainda não foi configurado.', ephemeral=True
                        )
                    return await inter.response.send_message(message_text, view=view, ephemeral=True)

                await inter.response.defer(ephemeral=True)
                success, message_text = await verify_member(inter.user, self.bot)
                prefix = emoji.correct if success else emoji.wrong
                await inter.followup.send(f'{prefix} {message_text}', ephemeral=True)
            case 'CloudMsgEdit_CycleStyle':
                cloud_config = db.get_document('cloud_data') or {}
                message_config = cloud_config.setdefault('message_verify', {})
                styles = ['embed', 'content', 'container']
                current_style = message_config.get('message_style', 'embed')
                try:
                    current_index = styles.index(current_style)
                    new_style = styles[(current_index + 1) % len(styles)]
                except ValueError:
                    new_style = 'embed'
                message_config['message_style'] = new_style
                db.save_document('cloud_data', cloud_config)
                await config_mensagem.show_panel(inter)
            case 'CloudMsgEdit_EditButton':
                cloud_config = db.get_document('cloud_data') or {}
                button_data = cloud_config.get('message_verify', {}).get('button', {})
                await inter.response.send_modal(config_mensagem.EditButtonModal(data=button_data))
            case 'CloudMsgEdit_EditContent':
                cloud_config = db.get_document('cloud_data') or {}
                message_config = cloud_config.get('message_verify', {})
                style = message_config.get('message_style', 'embed')
                try:
                    if style == 'embed':
                        embed_data = message_config.get('embed', {})
                        await inter.response.send_modal(config_mensagem.EditEmbedModal(data=embed_data))
                    elif style == 'content':
                        content_data = message_config.get('content', {})
                        await inter.response.send_modal(config_mensagem.EditContentModal(data=content_data))
                    else:
                        container_data = message_config.get('container', {})
                        await inter.response.send_modal(config_mensagem.EditContainerModal(data=container_data))
                except disnake.errors.NotFound:
                    try:
                        await inter.followup.send('A interação expirou. Clique novamente no botão.', ephemeral=True)
                    except Exception:
                        pass
                    return
            case 'CloudMsgEdit_Send':
                await config_mensagem.show_send_panel(inter, self.bot)
            case 'CloudMsgEdit_Preview':
                if not inter.response.is_done():
                    await inter.response.defer(ephemeral=True)
                cloud_config = db.get_document('cloud_data') or {}
                message_config = cloud_config.get('message_verify', {})
                style = message_config.get('message_style', 'embed')
                send_kwargs = {}
                if style == 'embed':
                    embed_data = message_config.get('embed', {})
                    if not embed_data:
                        embed_data = {'title': 'Título de Exemplo', 'description': 'Descrição de exemplo.'}
                    normalized_data = utils.normalize_embed_data(embed_data)
                    embed = disnake.Embed.from_dict(normalized_data)
                    send_kwargs['embed'] = embed
                elif style == 'content':
                    content_data = message_config.get('content', {})
                    send_kwargs['content'] = content_data.get('content', 'Conteúdo de exemplo.')
                elif style == 'container':
                    data = message_config.get('container', {})
                    container = config_mensagem.ContainerUtils.montar_container(conteudo=data.get('content'), imagem_url=data.get('image_url'), cor_hex=data.get('color'), thumbnail_url=data.get('thumbnail_url'))
                    send_kwargs['components'] = [container]
                    send_kwargs['flags'] = disnake.MessageFlags(is_components_v2=True)
                button_data = message_config.get('button', {})
                style_map = {'green': disnake.ButtonStyle.green, 'grey': disnake.ButtonStyle.grey, 'red': disnake.ButtonStyle.red, 'blue': disnake.ButtonStyle.primary}
                button = disnake.ui.Button(label=button_data.get('label', 'Verificar'), style=style_map.get(button_data.get('style', 'green')), emoji=config_mensagem.get_validated_emoji(button_data.get('emoji')), custom_id='do_nothing')
                view = disnake.ui.View()
                view.add_item(button)
                if style != 'container':
                    send_kwargs['view'] = view
                else:
                    if 'components' not in send_kwargs:
                        send_kwargs['components'] = []
                    send_kwargs['components'].append(disnake.ui.ActionRow(button))
                if style == 'container':
                    await inter.followup.send(**send_kwargs, ephemeral=True)
                else:
                    await inter.followup.send(**send_kwargs, ephemeral=True)
            case 'CloudSend_External':
                await inter.response.send_modal(config_mensagem.ExternalSendModal(self.bot))

    @commands.Cog.listener('on_dropdown')
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id.startswith('Cloud') and (not inter.component.custom_id.startswith('manage_gift_select')) and (not inter.component.custom_id.startswith('delete_gift_select')):
            return
        custom_id = inter.component.custom_id
        if custom_id == 'CloudTasks_Select':
            try:
                if not inter.response.is_done():
                    await inter.response.defer()
            except disnake.errors.HTTPException:
                pass
            try:
                if not inter.values:
                    try:
                        await inter.followup.send('Nenhuma task selecionada.', ephemeral=True)
                    except:
                        pass
                    return
                task_id = inter.values[0]
                mode = db.get_document('custom_mode').get('mode')
                if mode == 'embed':
                    try:
                        await embed_message.wait(inter, followup=True)
                    except:
                        pass
                    embed, components = TaskDetailsView_embed(inter, task_id)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                else:
                    try:
                        await message.wait(inter, followup=True)
                    except:
                        pass
                    components = TaskDetailsView_components(inter, task_id)
                    await inter.edit_original_message(components=components)
            except Exception as e:
                print(f'Erro no handler CloudTasks_Select: {e}')
                try:
                    await inter.followup.send(f'Erro ao processar seleção: {str(e)}', ephemeral=True)
                except:
                    pass
        elif custom_id.startswith('manage_gift_select'):
            await self._handle_manage_gift_select(inter)
        elif custom_id.startswith('delete_gift_select'):
            await self._handle_delete_gift_select(inter)
        elif custom_id == 'CloudDefinicoes_Select':
            try:
                if not inter.response.is_done():
                    await inter.response.defer()
            except disnake.errors.HTTPException:
                pass
            setting_key = inter.values[0]
            cloud_config = db.get_document('cloud_data') or {}
            definitions = cloud_config.setdefault('definitions', {})
            setting = definitions.setdefault(setting_key, {})
            setting['enabled'] = not setting.get('enabled', False)
            db.save_document('cloud_data', cloud_config)
            from .update_api import get_websocket_manager
            ws_manager = get_websocket_manager()
            try:
                if ws_manager.is_connected():
                    await ws_manager.update_definitions(definitions)
            except Exception as e:
                print(f'[Cloud Cog] Erro ao enviar definições: {e}')
            mode = db.get_document('custom_mode').get('mode')
            if mode == 'embed':
                embed, components = DefinicoesView_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                components = DefinicoesView_components(inter)
                await inter.edit_original_message(components=components)
        if inter.component.custom_id == 'CloudSend_ChannelSelect':
            try:
                if not inter.response.is_done():
                    await inter.response.defer()
            except disnake.errors.HTTPException:
                pass
            try:
                channel_id = int(inter.values[0])
                channel = self.bot.get_channel(channel_id)
            except (ValueError, IndexError):
                channel = None
            if not channel:
                if db.get_document('custom_mode').get('mode') == 'embed':
                    await inter.edit_original_message(content=f'{emoji.wrong} Canal não encontrado.', embed=None, components=[])
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.wrong}\n-# **Erro**'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay('Canal não encontrado.'))
                    await inter.edit_original_message(components=[container])
                return
            cloud_config = db.get_document('cloud_data') or {}
            message_config = cloud_config.get('message_verify', {})
            success, error_message = await config_mensagem._send_verification_message(channel, message_config)
            if success:
                if db.get_document('custom_mode').get('mode') == 'embed':
                    await inter.edit_original_message(content=f'{emoji.correct} Mensagem de verificação enviada para {channel.mention}.', embed=None, components=[])
                else:
                    container = disnake.ui.Container(disnake.ui.TextDisplay(f'{emoji.correct} Mensagem de verificação enviada para {channel.mention}.'))
                    await inter.edit_original_message(components=[container])
            elif db.get_document('custom_mode').get('mode') == 'embed':
                await inter.edit_original_message(content=f'{emoji.wrong} {error_message}', embed=None, components=[])
            else:
                container = disnake.ui.Container(disnake.ui.TextDisplay(f'{emoji.wrong} {error_message}'))
                await inter.edit_original_message(components=[container])

def setup(bot: commands.Bot):
    bot.add_cog(Cloud(bot))
