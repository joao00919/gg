import disnake
from disnake.ext import commands
import aiohttp
import json
import os
from functions.emoji import emoji
from functions.database import database as db
from functions.message import message, embed_message

class SyncGenConfig(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = os.getenv('ZYNEXGEN_API_URL', '').strip().rstrip('/')
        self.bot_secret = os.getenv('ZYNEXGEN_BOT_SECRET', '').strip()

    def _get_integration_status(self) -> dict:
        """Obtém status da integração"""
        return db.obter('database/syncgen.json')

    async def display_panel(self, inter: disnake.MessageInteraction):
        await self._check_pending_codes()
        mode = db.get_document('custom_mode').get('mode')
        if mode == 'embed':
            await embed_message.wait(inter, send=False)
            embed, components = self.panel_embed(inter)
            await inter.edit_original_message(content=None, embed=embed, components=components)
        else:
            await message.wait(inter, send=False)
            components = self.panel_components(inter)
            await inter.edit_original_message(components=components)

    async def _check_pending_codes(self):
        """Verifica se há códigos pendentes que já foram resgatados"""
        status_data = db.obter('database/syncgen.json')
        pending_code = status_data.get('pending_code')
        if not pending_code:
            return
        if status_data.get('integrated_user_id'):
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{self.api_url}/bot/check-code/{pending_code}', headers={'x-bot-secret': self.bot_secret}) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('redeemed'):
                            username = data.get('username')
                            user_id = data.get('redeemedBy')
                            status_data['integrated_user'] = username
                            status_data['integrated_user_id'] = user_id
                            status_data['pending_code'] = None
                            db.salvar('database/syncgen.json', status_data)
        except Exception:
            pass

    def panel_components(self, inter: disnake.MessageInteraction) -> list:
        """Constrói painel em modo components"""
        colors = db.get_document('custom_colors')
        primary_color_hex = colors.get('primary')
        status_data = self._get_integration_status()
        integrated_user = status_data.get('integrated_user', 'Nenhum')
        is_integrated = status_data.get('integrated_user_id') is not None
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace('#', ''), 16)
            container_kwargs['accent_colour'] = disnake.Colour(primary_color)
        options = [disnake.SelectOption(label='Gerar Código', value='generate_code', emoji=emoji.link, description='Gera um código para vincular ao painel'), disnake.SelectOption(label='Selecionar Projeto', value='select_project', emoji=emoji.folder, description='Define um projeto padrão para requisições'), disnake.SelectOption(label='Configurar Sistema', value='configure_system', emoji=emoji.settings, description='Acessar configurações avançadas (Requer integração)' if not is_integrated else 'Gerenciar configurações avançadas'), disnake.SelectOption(label='Tutorial', value='tutorial', emoji=emoji.fire, description='Aprenda a usar a extensão')]
        return [disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Painel > Configurações > **Sync Gen**\n'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay(f"""-# Painel de controle completo para o Sync Gen.\n{emoji.on} **Status:** Ativo\n{emoji.member} **Usuário Integrado:** `{integrated_user}`\n{(f"{emoji.folder} **Projeto Selecionado:** `{status_data.get('project_key')}`" if status_data.get('project_key') else '')}"""), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id='SyncGen_Select', placeholder='Selecione uma ação', options=options)), **container_kwargs), disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='Configuracoes_Extensoes'), disnake.ui.Button(label='Desativar' if status_data.get('enabled', True) else 'Ativar', style=disnake.ButtonStyle.red if status_data.get('enabled', True) else disnake.ButtonStyle.green, emoji=emoji.off if status_data.get('enabled', True) else emoji.on, custom_id='SyncGen_Toggle'))]

    def panel_embed(self, inter: disnake.MessageInteraction) -> tuple:
        """Constrói painel em modo embed"""
        colors = db.get_document('custom_colors')
        primary_color_hex = colors.get('primary')
        status_data = self._get_integration_status()
        integrated_user = status_data.get('integrated_user', 'Nenhum')
        embed = disnake.Embed(title=f'{emoji.commands} Sync Gen', description=f"""-# Painel de controle completo para o Sync Gen.{emoji.on} **Status:** Ativo\n{emoji.member} **Usuário Integrado:** `{integrated_user}`\n{(f"{emoji.folder} **Projeto Selecionado:** `{status_data.get('project_key')}`" if status_data.get('project_key') else '')}""")
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace('#', ''), 16)
            embed.color = primary_color
        options = [disnake.SelectOption(label='Gerar Código', value='generate_code', emoji=emoji.link, description='Gera um código para vincular ao painel'), disnake.SelectOption(label='Selecionar Projeto', value='select_project', emoji=emoji.folder, description='Define um projeto padrão para requisições'), disnake.SelectOption(label='Configurar Sistema', value='configure_system', emoji=emoji.settings, description='Configurações do sistema'), disnake.SelectOption(label='Tutorial', value='tutorial', emoji='📚', description='Aprenda a usar a extensão')]
        components = [disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id='SyncGen_Select', placeholder='Selecione uma ação', options=options)), disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='Configuracoes_Extensoes'), disnake.ui.Button(label='Desativar' if status_data.get('enabled', True) else 'Ativar', style=disnake.ButtonStyle.red if status_data.get('enabled', True) else disnake.ButtonStyle.green, emoji=emoji.off if status_data.get('enabled', True) else emoji.on, custom_id='SyncGen_Toggle'))]
        return (embed, components)

    async def _generate_code(self, inter: disnake.MessageInteraction):
        await inter.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'{self.api_url}/bot/generate-code', headers={'x-bot-secret': self.bot_secret}, json={'discordId': str(self.bot.user.id)}) as response:
                    if response.status == 200:
                        data = await response.json()
                        code = data.get('code')
                        status_data = db.obter('database/syncgen.json')
                        status_data['pending_code'] = code
                        db.salvar('database/syncgen.json', status_data)
                        await inter.followup.send(content=f'Seu código de vinculação é: **{code}**\nInsira este código no painel para vincular o bot.', ephemeral=True)
                    else:
                        await inter.followup.send(content=f'Erro ao gerar código: {response.status}', ephemeral=True)
        except Exception as e:
            await inter.followup.send(content=f'Erro de conexão: {str(e)}', ephemeral=True)

    @commands.Cog.listener('on_dropdown')
    async def on_syncgen_dropdown(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == 'SyncGen_Select':
            choice = inter.values[0]
            if choice == 'generate_code':
                await self._generate_code(inter)
            elif choice == 'select_project':
                await inter.response.defer()
                await self._select_project_menu(inter)
            elif choice == 'configure_system':
                await self._configure_system_menu(inter)
            elif choice == 'tutorial':
                tutorial_text = f"# {emoji.fire} Tutorial de Uso\n\n**Como resgatar o código:**\n1. Faça login no site [Loop Gen](https://loopgen.vercel.app).\n2. Vá em **Integrar Sync Bot**.\n3. Cole o código gerado pelo bot (Opção 'Gerar Código').\n\n**Como criar um projeto:**\n1. No site, clique em **Novo Projeto**.\n2. Dê um nome ao projeto e uma chave (Key) de 6 caracteres.\n3. Clique em **Create Project**.\n4. No bot, vá em **Selecionar Projeto** e escolha o projeto criado."
                await inter.response.send_message(tutorial_text, ephemeral=True)
        elif inter.component.custom_id == 'SyncGen_SystemSelect':
            choice = inter.values[0]
            if choice == 'gen_streaming_gaming':
                await inter.response.send_modal(ServiceModal(self))
            elif choice in ['live_stock', 'activate_gen', 'custom_embeds']:
                await inter.response.send_message('Funcionalidade em breve...', ephemeral=True)
        elif inter.component.custom_id == 'SyncGen_ProjectSelect':
            val = inter.values[0]
            key = val.replace('proj_', '')
            current_data = db.obter('database/syncgen.json')
            current_data['project_key'] = key
            db.salvar('database/syncgen.json', current_data)
            await inter.response.send_message(f'Projeto selecionado com sucesso! Key: `{key}`', ephemeral=True)

    async def _select_project_menu(self, inter: disnake.MessageInteraction):
        status_data = self._get_integration_status()
        if not status_data.get('integrated_user_id'):
            await inter.response.send_message('Você precisa vincular o bot a um usuário primeiro.', ephemeral=True)
            return
        discord_id = status_data.get('integrated_user_id')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{self.api_url}/projects/user/{discord_id}', headers={'x-bot-secret': self.bot_secret}) as response:
                    if response.status == 200:
                        data = await response.json()
                        projects = data.get('projects', [])
                        if not projects:
                            await inter.response.send_message('Você não possui projetos criados no painel.', ephemeral=True)
                            return
                        options = []
                        for p in projects:
                            options.append(disnake.SelectOption(label=p.get('name'), value=f"proj_{p.get('key')}", description=f"Key: {p.get('key')}", emoji=emoji.folder))
                        colors = db.get_document('custom_colors')
                        primary_color_hex = colors.get('primary')
                        container_kwargs = {}
                        if primary_color_hex:
                            primary_color = int(primary_color_hex.replace('#', ''), 16)
                            container_kwargs['accent_colour'] = disnake.Colour(primary_color)
                        components = [disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Sync Gen > **Projetos**\n'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay(f'-# Selecione um projeto padrão para usar nas requisições.'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id='SyncGen_ProjectSelect', placeholder='Selecione um projeto', options=options)), **container_kwargs), disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='SyncGen_BackToMain'))]
                        await inter.edit_original_message(components=components)
                    else:
                        await inter.response.send_message(f'Erro ao buscar projetos: {response.status}', ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f'Erro de conexão: {str(e)}', ephemeral=True)

    async def _configure_system_menu(self, inter: disnake.MessageInteraction):
        status_data = self._get_integration_status()
        if not status_data.get('integrated_user_id'):
            await inter.response.send_message('Você precisa vincular o bot a um usuário no painel antes de configurar o sistema.', ephemeral=True)
            return
        colors = db.get_document('custom_colors')
        primary_color_hex = colors.get('primary')
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace('#', ''), 16)
            container_kwargs['accent_colour'] = disnake.Colour(primary_color)
        options = [disnake.SelectOption(label='Gerar Streaming/Gaming', value='gen_streaming_gaming', emoji=emoji.controller, description='Configurar gerador de contas'), disnake.SelectOption(label='Ativar Live-Stock em Produtos', value='live_stock', emoji=emoji.cart, description='Em breve'), disnake.SelectOption(label='Ativar comando /gen e sistemas', value='activate_gen', emoji=emoji.commands, description='Em breve'), disnake.SelectOption(label='Personalizar Embeds', value='custom_embeds', emoji=emoji.paint, description='Em breve')]
        components = [disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.z0}\n-# Sync Gen > **Configurações**\n'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.TextDisplay(f'-# Selecione uma opção para configurar.'), disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small), disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id='SyncGen_SystemSelect', placeholder='Selecione uma configuração', options=options)), **container_kwargs), disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id='SyncGen_BackToMain'))]
        await inter.response.edit_message(components=components)

    async def _show_gen_category_selection(self, inter: disnake.MessageInteraction):
        options = [disnake.SelectOption(label='Gaming', value='gaming', emoji=emoji.controller), disnake.SelectOption(label='Streaming', value='streaming', emoji=emoji.play)]
        components = [disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id='SyncGen_CategorySelect', placeholder='Selecione a categoria', options=options))]
        await inter.response.send_message('-# Selecione a categoria do serviço:', components=components, ephemeral=True)

    @commands.Cog.listener('on_button_click')
    async def on_syncgen_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        if custom_id == 'SyncGen_BackToMain':
            await self.display_panel(inter)
        elif custom_id == 'SyncGen_BackToSystem':
            await self._configure_system_menu(inter)
        elif custom_id.startswith('SyncGen_OpenServiceModal_'):
            category = custom_id.replace('SyncGen_OpenServiceModal_', '')
            await inter.response.send_modal(ServiceModal(category))
        elif custom_id.startswith('check_code_'):
            code = custom_id.replace('check_code_', '')
            await inter.response.defer(ephemeral=True)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f'{self.api_url}/bot/check-code/{code}', headers={'x-bot-secret': self.bot_secret}) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('redeemed'):
                                username = data.get('username')
                                user_id = data.get('redeemedBy')
                                current_data = db.obter('database/syncgen.json')
                                current_data['integrated_user'] = username
                                current_data['integrated_user_id'] = user_id
                                current_data['project_key'] = None
                                db.salvar('database/syncgen.json', current_data)
                                await inter.followup.send(f'Sucesso! Bot vinculado ao usuário: **{username}**', ephemeral=True)
                            else:
                                await inter.followup.send('Este código ainda não foi reivindicado.', ephemeral=True)
                        else:
                            await inter.followup.send(f'Erro ao verificar código: {response.status}', ephemeral=True)
            except Exception as e:
                await inter.followup.send(f'Erro de conexão: {str(e)}', ephemeral=True)
        elif custom_id == 'SyncGen_Toggle':
            current_data = db.obter('database/syncgen.json')
            is_enabled = current_data.get('enabled', True)
            current_data['enabled'] = not is_enabled
            db.salvar('database/syncgen.json', current_data)
            await self.display_panel(inter)
        elif custom_id == 'SyncGen_Tutorial':
            tutorial_text = f"# {emoji.fire} Tutorial de Uso\n\n**Como resgatar o código:**\n1. Faça login no site [Loop Gen](https://loopgen.vercel.app).\n2. Vá em **Integrar Sync Bot**.\n3. Cole o código gerado pelo bot (Opção 'Gerar Código').\n\n**Como criar um projeto:**\n1. No site, clique em **Novo Projeto**.\n2. Dê um nome ao projeto e uma chave (Key) de 6 caracteres.\n3. Clique em **Create Project**.\n4. No bot, vá em **Selecionar Projeto** e escolha o projeto criado."
            await inter.response.send_message(tutorial_text, ephemeral=True)

class ServiceModal(disnake.ui.Modal):

    def __init__(self, cog):
        self.cog = cog
        components = [disnake.ui.TextInput(label='Nome do Serviço', placeholder='Ex: Netflix, Spotify, Steam...', custom_id='service_name', style=disnake.TextInputStyle.short, max_length=50), disnake.ui.Label(text='Categoria', component=disnake.ui.StringSelect(placeholder='Selecione a categoria', custom_id='category_select', options=[disnake.SelectOption(label='Streaming', value='streaming', emoji=emoji.play), disnake.SelectOption(label='Gaming', value='gaming', emoji=emoji.controller)], min_values=1, max_values=1), description='Selecione a categoria do serviço.')]
        super().__init__(title='Gerar Contas', components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        service_name = inter.text_values['service_name']
        category = 'streaming'
        if hasattr(inter, 'resolved_values'):
            cat_val = inter.resolved_values.get('category_select')
            if cat_val:
                category = cat_val[0] if isinstance(cat_val, list) else cat_val
        else:
            for component in inter.data.get('components', []):
                for child in component.get('components', []):
                    if child.get('custom_id') == 'category_select':
                        if 'values' in child:
                            category = child['values'][0]
        data = db.obter('database/syncgen.json')
        project_key = data.get('project_key')
        if not project_key:
            await inter.response.send_message('Erro: Nenhum projeto selecionado. Selecione um projeto nas configurações primeiro.', ephemeral=True)
            return
        await inter.response.send_message('Enviarei um .txt no seu privado quando eu terminar de gerar as contas!', ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'{self.cog.api_url}/scrape-project', headers={'x-project-key': project_key}, json={'service': service_name, 'category': category, 'threads': 1, 'timeout': 600000}, timeout=None) as response:
                    if response.status == 200:
                        result = await response.json()
                        credentials = result.get('credentials', [])
                        count = len(credentials)
                        if count > 0:
                            if isinstance(credentials, dict):
                                content = '\n'.join([f'{email}:{password}' for email, password in credentials.items()])
                            else:
                                content = '\n'.join([f"{c.get('email')}:{c.get('password')}" for c in credentials])
                            import io
                            file = disnake.File(io.BytesIO(content.encode('utf-8')), filename=f'{service_name}_contas.txt')
                            try:
                                components = [disnake.ui.Container(disnake.ui.TextDisplay(f'# {emoji.correct} Geração Concluída!\n\n{emoji.website} **Serviço:** `{service_name}`\n{emoji.folder} **Categoria:** `{category.capitalize()}`\n{emoji.cart} **Quantidade:** `{count}`'))]
                                await inter.author.send(components=components)
                                await inter.author.send(file=file)
                                await inter.edit_original_message(content=f'**Sucesso!** As contas foram enviadas no seu privado.')
                            except disnake.Forbidden:
                                await inter.edit_original_message(content=f'⚠️ **Atenção:** Gere {count} contas, mas não consegui te enviar no privado. Verifique suas configurações de privacidade.')
                        else:
                            await inter.edit_original_message(content=f'⚠️ **Aviso:** O processo terminou, mas nenhuma conta foi encontrada para **{service_name}**.')
                    else:
                        text = await response.text()
                        try:
                            err_json = json.loads(text)
                            err_msg = err_json.get('error', text)
                        except:
                            err_msg = text
                        await inter.edit_original_message(content=f'❌ **Erro na API:** {response.status}\n{err_msg}')
        except Exception as e:
            await inter.edit_original_message(content=f'❌ **Erro de conexão:** {str(e)}')

def setup(bot: commands.Bot):
    bot.add_cog(SyncGenConfig(bot))
