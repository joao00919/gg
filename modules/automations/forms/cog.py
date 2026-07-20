import disnake
from disnake.ext import commands
from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
from functions.utils import utils
from . import helpers
from .edit_form import EditFormView_components, EditFormView_embed, SpecificFormView_components, SpecificFormView_embed

class CreateFormModal(disnake.ui.Modal):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        components = [
            disnake.ui.TextInput(
                label="Nome do Formulário",
                placeholder="Ex: Aplicação para Staff",
                custom_id="form_name",
                max_length=50,
            ),
        ]
        super().__init__(title="Criar Novo Formulário", components=components, custom_id="create_form_modal")

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter, send=False)
        else:
            await message.wait(inter, send=False)
        
        form_id = utils.gerar_id()
        form_name = inter.text_values["form_name"]

        config = helpers.carregar_config()
        if "forms" not in config:
            config["forms"] = {}
            
        config["forms"][form_id] = {
            "name": form_name
        }
        helpers.salvar_config(config)
        
        # After creating, refresh the main panel
        if mode == "components":
            await inter.edit_original_message(components=FormsCog.Painel())
        else:
            embed, components = FormsCog.PainelEmbed()
            await inter.edit_original_message(content=None, embed=embed, components=components)

class FormMessageModal(disnake.ui.Modal):
    def __init__(self, form_id: str, data: dict):
        self.form_id = form_id
        message_data = data.get("message") or {}
        super().__init__(
            title="Mensagem do formulário",
            custom_id=f"form_message_modal:{form_id}",
            components=[
                disnake.ui.TextInput(label="Título", custom_id="title", value=str(message_data.get("title") or data.get("name") or "")[:100], max_length=100),
                disnake.ui.TextInput(label="Descrição", custom_id="description", value=str(message_data.get("description") or "")[:2000], style=disnake.TextInputStyle.paragraph, required=False, max_length=2000),
                disnake.ui.TextInput(label="Texto do botão", custom_id="button_label", value=str(message_data.get("button_label") or "Responder")[:30], max_length=30),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        config = helpers.carregar_config()
        form = (config.get("forms") or {}).get(self.form_id)
        if not form:
            await inter.response.send_message(f"{emoji.wrong} Formulário não encontrado.", ephemeral=True)
            return
        form["message"] = {
            "title": inter.text_values["title"].strip(),
            "description": inter.text_values.get("description", "").strip(),
            "button_label": inter.text_values["button_label"].strip(),
        }
        helpers.salvar_config(config)
        await inter.response.send_message(f"{emoji.correct} Mensagem do formulário atualizada.", ephemeral=True)


class FormQuestionsModal(disnake.ui.Modal):
    def __init__(self, form_id: str, data: dict):
        self.form_id = form_id
        existing = []
        for question in data.get("questions") or []:
            existing.append(f"{question.get('label', '')}|{question.get('style', 'short')}|{'sim' if question.get('required', True) else 'nao'}")
        super().__init__(
            title="Perguntas do formulário",
            custom_id=f"form_questions_modal:{form_id}",
            components=[
                disnake.ui.TextInput(
                    label="Uma pergunta por linha",
                    custom_id="questions",
                    placeholder="Nome completo|short|sim\nPor que deseja entrar?|paragraph|sim",
                    value="\n".join(existing)[:4000],
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=4000,
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        config = helpers.carregar_config()
        form = (config.get("forms") or {}).get(self.form_id)
        if not form:
            await inter.response.send_message(f"{emoji.wrong} Formulário não encontrado.", ephemeral=True)
            return
        questions = []
        for index, raw_line in enumerate(inter.text_values["questions"].splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split("|")]
            label = parts[0]
            style = parts[1].lower() if len(parts) > 1 else "short"
            required_text = parts[2].lower() if len(parts) > 2 else "sim"
            if not label or style not in {"short", "paragraph"}:
                await inter.response.send_message(f"{emoji.wrong} Linha {index} inválida. Use `Pergunta|short|sim`.", ephemeral=True)
                return
            questions.append({"id": str(index), "label": label[:100], "style": style, "required": required_text in {"sim", "s", "true", "1"}})
        if not questions or len(questions) > 5:
            await inter.response.send_message(f"{emoji.wrong} Configure entre 1 e 5 perguntas por formulário.", ephemeral=True)
            return
        form["questions"] = questions
        helpers.salvar_config(config)
        await inter.response.send_message(f"{emoji.correct} {len(questions)} pergunta(s) salva(s).", ephemeral=True)


class FormAdvancedModal(disnake.ui.Modal):
    def __init__(self, form_id: str, data: dict):
        self.form_id = form_id
        settings = data.get("settings") or {}
        super().__init__(
            title="Configurações do formulário",
            custom_id=f"form_advanced_modal:{form_id}",
            components=[
                disnake.ui.TextInput(label="Canal de respostas (ID)", custom_id="channel_id", value=str(settings.get("channel_id") or ""), required=False, max_length=20),
                disnake.ui.TextInput(label="Limite por usuário", custom_id="max_per_user", value=str(settings.get("max_per_user") or 1), max_length=4),
                disnake.ui.TextInput(label="Mensagem após envio", custom_id="success_message", value=str(settings.get("success_message") or "Resposta enviada com sucesso.")[:500], style=disnake.TextInputStyle.paragraph, max_length=500),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        config = helpers.carregar_config()
        form = (config.get("forms") or {}).get(self.form_id)
        if not form:
            await inter.response.send_message(f"{emoji.wrong} Formulário não encontrado.", ephemeral=True)
            return
        channel_id = inter.text_values.get("channel_id", "").strip()
        if channel_id and (not channel_id.isdigit() or not inter.guild.get_channel(int(channel_id))):
            await inter.response.send_message(f"{emoji.wrong} Informe um canal válido deste servidor.", ephemeral=True)
            return
        try:
            max_per_user = int(inter.text_values.get("max_per_user", "1"))
            if not 1 <= max_per_user <= 9999:
                raise ValueError
        except ValueError:
            await inter.response.send_message(f"{emoji.wrong} O limite por usuário deve estar entre 1 e 9999.", ephemeral=True)
            return
        form["settings"] = {
            "channel_id": int(channel_id) if channel_id else None,
            "max_per_user": max_per_user,
            "success_message": inter.text_values.get("success_message", "").strip(),
        }
        helpers.salvar_config(config)
        await inter.response.send_message(f"{emoji.correct} Configurações gerais atualizadas.", ephemeral=True)


class FormsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @staticmethod
    def Painel() -> list[disnake.ui.Container]:
        config = helpers.carregar_config()
        ativado = config.get("ativado", False)
        forms = config.get("forms", {})
        form_count = len(forms)
        
        resumo = (
            f"{emoji.on if ativado else emoji.off} **Status:** `{'Ativado' if ativado else 'Desativado'}`\n"
            f"{emoji.receipt} **Formulários Criados:** `{form_count}`\n"
        )

        botoes_principais = [
            disnake.ui.Button(label="", style=disnake.ButtonStyle.grey, emoji=emoji.power, custom_id="Forms_ToggleAtivo"),
            disnake.ui.Button(label="Adicionar", style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id="Forms_Adicionar", disabled=not ativado),
            disnake.ui.Button(label="Editar", style=disnake.ButtonStyle.grey, emoji=emoji.edit, custom_id="Forms_Editar", disabled=form_count == 0 or not ativado),
        ]
        
        primary_color_hex = db.get_document("custom_colors").get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Automações > **Formulários**"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay("Crie formulários personalizados para os membros preencherem."),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(resumo),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(*botoes_principais),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarAutomações"),
            )
        ]

    @staticmethod
    def PainelEmbed() -> tuple[disnake.Embed, list[disnake.ui.ActionRow]]:
        config = helpers.carregar_config()
        ativado = config.get("ativado", False)
        forms = config.get("forms", {})
        form_count = len(forms)

        resumo = (
            f"{emoji.on if ativado else emoji.off} **Status:** `{'Ativado' if ativado else 'Desativado'}`\n"
            f"{emoji.receipt} **Formulários Criados:** `{form_count}`\n"
        )

        primary_color_hex = db.get_document("custom_colors").get("primary")
        embed = disnake.Embed(
            title=f"Formulários",
            description="Crie formulários personalizados para os membros preencherem."
        )
        if primary_color_hex:
            embed.color = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
        
        embed.add_field(name="Configurações", value=resumo, inline=False)

        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="", style=disnake.ButtonStyle.grey, emoji=emoji.power, custom_id="Forms_ToggleAtivo"),
                disnake.ui.Button(label="Adicionar", style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id="Forms_Adicionar", disabled=not ativado),
                disnake.ui.Button(label="Editar", style=disnake.ButtonStyle.grey, emoji=emoji.edit, custom_id="Forms_Editar", disabled=form_count == 0 or not ativado),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarAutomações"),
            )
        ]
        return embed, components

    @commands.Cog.listener("on_button_click")
    async def Forms_Button_Listener(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        if custom_id == "Forms_ToggleAtivo":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter, send=False)
            else:
                await message.wait(inter, send=False)
            
            config = helpers.carregar_config()
            config["ativado"] = not config.get("ativado", False)
            helpers.salvar_config(config)
            
            if mode == "embed":
                embed, components = self.PainelEmbed()
                await inter.response.edit_message(content=None, embed=embed, components=components)
            else:
                await inter.response.edit_message(components=self.Painel())

        elif custom_id == "Forms_Adicionar":
            await inter.response.send_modal(CreateFormModal(self.bot))

        elif custom_id == "Forms_Editar":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter)
                embed, components = EditFormView_embed()
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter)
                components = EditFormView_components()
                await inter.edit_original_message(components=components)
        
        elif custom_id == "Forms_Painel":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter)
                embed, components = self.PainelEmbed()
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter)
                await inter.edit_original_message(components=self.Painel())

        elif custom_id.startswith("FormEdit_"):
            try:
                _, action, form_id = custom_id.split("_", 2)
            except ValueError:
                await inter.response.send_message(f"{emoji.wrong} Ação de formulário inválida.", ephemeral=True)
                return
            config = helpers.carregar_config()
            form_data = (config.get("forms") or {}).get(form_id)
            if not form_data:
                await inter.response.send_message(f"{emoji.wrong} Formulário não encontrado.", ephemeral=True)
                return
            if action == "SetMessage":
                await inter.response.send_modal(FormMessageModal(form_id, form_data))
            elif action == "SetQuestions":
                await inter.response.send_modal(FormQuestionsModal(form_id, form_data))
            elif action == "Advanced":
                await inter.response.send_modal(FormAdvancedModal(form_id, form_data))
            elif action == "Stats":
                responses = form_data.get("responses") or []
                users = {str(item.get("user_id")) for item in responses if isinstance(item, dict) and item.get("user_id")}
                embed = disnake.Embed(
                    title=f"Estatísticas — {form_data.get('name', 'Formulário')}",
                    description=(
                        f"**Respostas:** {len(responses)}\n"
                        f"**Usuários únicos:** {len(users)}\n"
                        f"**Perguntas configuradas:** {len(form_data.get('questions') or [])}"
                    ),
                    color=disnake.Color.blurple(),
                )
                await inter.response.send_message(embed=embed, ephemeral=True)


    @commands.Cog.listener("on_dropdown")
    async def Forms_Dropdown_Listener(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id

        if custom_id.startswith("select_form_to_edit_"):
            form_id = inter.values[0]
            if form_id == "disabled":
                await inter.response.defer()
                return

            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter)
                embed, components = SpecificFormView_embed(form_id)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter)
                components = SpecificFormView_components(form_id)
                await inter.edit_original_message(components=components)


def setup(bot: commands.Bot):
    bot.add_cog(FormsCog(bot))
