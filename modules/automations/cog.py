import disnake
from disnake.ext import commands

from functions.emoji import emoji
from functions.message import message, embed_message
from functions.interaction_runtime import respond_panel
from .boas_vindas.cog import BoasVindasConfig
from .cont_members.cog import ContMembrosCog
from .ai_moderator.cog import AIModeratorCog
from .clean.cog import CleanCog
from .ai_chat.cog import AIChatCog
from .feedbacks.cog import FeedbacksCog
from .cont_members_call.cog import ContMembrosCallCog
from .cont_vendas.cog import ContVendasCog
from .invite_tracker.cog import InviteTrackerCog
from .lock_unlock.cog import LockUnlockCog
from .msg_auto.cog import MsgAutoCog
from .reactions.cog import ReacoesCog, ReacoesUI
from .reactions.helpers import ReacoesDB
from functions.database import database as db
from .response_auto.cog import RespAutomaticasCog, RespAutomaticasUI, RespAutomaticasDB
from .suggestions.cog import SuggestionsCog, SuggestionsUI
from .suggestions.helpers import SuggestionsDB
from .topics.cog import TopicsCog
from .topics.helpers import TopicsDB
from .nuke.cog import NukeCog
from .forms.cog import FormsCog
from .repost.cog import RepostCog


AUTOMATION_MODULES = [
    "modules.automations.business_rules",
    "modules.automations.boas_vindas",
    "modules.automations.cont_members",
    "modules.automations.ai_moderator",
    "modules.automations.ai_chat",
    "modules.automations.clean",
    "modules.automations.feedbacks",
    "modules.automations.cont_members_call",
    "modules.automations.cont_vendas",
    "modules.automations.invite_tracker",
    "modules.automations.lock_unlock",
    "modules.automations.msg_auto",
    "modules.automations.reactions",
    "modules.automations.response_auto",
    "modules.automations.suggestions",
    "modules.automations.topics",
    "modules.automations.nuke",
    "modules.automations.repost",
    #"modules.automations.forms",
    #"modules.automations.cartas",
    #"modules.automations.temp_em_call",
    #"modules.automations.instagram",
]

def _get_automation_options():
        return [

                            disnake.SelectOption(label="Regras da Loja", value="regras_negocio", description="Estoque, pagamentos e tickets automáticos", emoji=emoji.route),

                            # Bem-vindas e Membros
                            disnake.SelectOption(label="ZYNEX AI Chat", value="ia_chat", description="Tenha um chat com IA em seu servidor", emoji=emoji.double_speech),
                            disnake.SelectOption(label="ZYNEX AI Moderator", value="filtro_tos", description="Tenha um moderador com IA em seu servidor", emoji=emoji.sparkles),
                            disnake.SelectOption(label="Boas-Vindas", value="boasvindas", description="Envie mensagens de boas-vindas aos novos membros", emoji=emoji.members),
                            disnake.SelectOption(label="Invite Tracker", value="invite_tracker", description="Rastreie convites de membros no servidor", emoji=emoji.telegram),
                            disnake.SelectOption(label="Contador de Membros (por Cargo)", value="contador_membros", description="Realiza a contagem de membros por cargo", emoji=emoji.role),
                            disnake.SelectOption(label="Contador de Membros (em Call)", value="contador_membros_call", description="Realiza a contagem de membros em call", emoji=emoji.voice),
                            disnake.SelectOption(label="Contador de Vendas", value="contador_vends", description="Realiza a contagem de vendas do bot", emoji=emoji.dollar),

                            # Moderação e Segurança
                            disnake.SelectOption(label="Monitoramento de Feedbacks", value="feedbacks", description="Monitora feedbacks negativos e alerta os admins", emoji=emoji.shield_star),
                            disnake.SelectOption(label="Auto Nuke", value="nuke", description="Reecrie canais automáticamente após um intervalo", emoji=emoji.wand),
                            disnake.SelectOption(label="Limpeza Automática", value="limpeza_canais", description="Limpe canais automáticamente após um intervalo", emoji=emoji.delete),
                            disnake.SelectOption(label="Auto-Lock", value="lock_unlock_canais", description="Tranque ou destranche canais automáticamente", emoji=emoji.lock),
                            

                            # Automação de Mensagens
                            disnake.SelectOption(label="Mensagens Automáticas", value="mensagens_auto", description="Envie mensagens automáticas em canais", emoji=emoji.message),
                            disnake.SelectOption(label="Tópicos Automáticos", value="topicos", description="Crie tópicos automáticos em mensagens", emoji=emoji.textc),
                            disnake.SelectOption(label="Reações Automáticas", value="reacoes", description="Envie reações automáticas a mensagens ou canais", emoji=emoji.reaction_add),
                            disnake.SelectOption(label="Respostas Automáticas", value="respostas_auto", description="Envie respostas automáticas a mensagens", emoji=emoji.reload),
                            disnake.SelectOption(label="Sistema de Repostagem", value="repostagem", description="Reposte produtos automáticamente", emoji=emoji.cardbox),
                            
                            # Sistemas
                            disnake.SelectOption(label="Sistema de Sugestões", value="sugestoes", description="Receba sugestões em um canal com sistema de votação", emoji=emoji.like),
                            disnake.SelectOption(label="Autorole Avançado (Em breve)", value="autorole", description="Adicione e remova cargos automaticamente", emoji=emoji.double_check),
                            disnake.SelectOption(label="Sistema de Formulários (Em breve)", value="formularios", description="Crie formulários personalizados dentro do servidor", emoji=emoji.receipt),
                            disnake.SelectOption(label="Sistema de Parcerias (Em breve)", value="parcerias", description="Realize parcerias automáticas com servidores", emoji=emoji.partner),
                            disnake.SelectOption(label="Sistema de Gifts (Em breve)", value="gifts", description="Envie gifts automáticamente sobre requisitos", emoji=emoji.gift2),
                            disnake.SelectOption(label="Sistema de Instagram (Em breve)", value="instagram", description="Tenha um instagram dentro do servidor", emoji=emoji.heart2),
                            disnake.SelectOption(label="Sistema de Cartas (Em breve)", value="cartas", description="Sistema de cartas para os membros utilizarem", emoji=emoji.mail2),

    ]

class AutomationModulesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        for module in AUTOMATION_MODULES:
            try:
                self.bot.reload_extension(module)
            except commands.ExtensionNotLoaded:
                try:
                    self.bot.load_extension(module)
                except Exception as e:
                    print(f"Falha ao carregar o módulo de automação '{module}': {e}")
            except Exception as e:
                print(f"Falha ao recarregar o módulo de automação '{module}': {e}")

    async def display_automations_panel(self, inter: disnake.MessageInteraction):
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            embed, components = self.PainelEmbed()
            panel = {"embed": embed, "components": components}
        else:
            panel = {"components": self.PainelComponents()}
        return await respond_panel(inter, panel, prefer_edit=True)

    @staticmethod
    def PainelComponents() -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > **Automações**"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay("Configure e personalize as automações do bot de acordo com suas necessidades."),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.Select(
                        placeholder="Selecione uma seção para configurar",
                        options=_get_automation_options(),
                        custom_id="AutomacoesSelect",
                        min_values=1,
                        max_values=1,
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarPainel"),
            )
        ]

    @staticmethod
    def PainelEmbed() -> tuple[disnake.Embed, list[disnake.ui.ActionRow]]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        embed = disnake.Embed(
            title=f"Automações",
            description="Configure e personalize as automações do bot de acordo com suas necessidades."
        )
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            embed.color = primary_color
        
        components = [
            disnake.ui.ActionRow(
                disnake.ui.Select(
                    placeholder="Selecione uma seção para configurar",
                    options=_get_automation_options(),
                    custom_id="AutomacoesSelect",
                    min_values=1,
                    max_values=1,
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarPainel"),
            )
        ]
        return embed, components

    @commands.Cog.listener("on_button_click")
    async def automations_button_listener(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "VoltarAutomações":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = AutomationModulesCog.PainelEmbed()
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                components = AutomationModulesCog.PainelComponents()
                await inter.edit_original_message(components=components)

        elif inter.component.custom_id == "VoltarPainel":
            from commands.admin.painel import PainelCommand
            painel_command = PainelCommand(self.bot)
            mode = db.get_document("custom_mode").get("mode")

            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = painel_command.PainelEmbed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                components = painel_command.PainelComponents(inter)
                await inter.edit_original_message(components=components)

    @commands.Cog.listener("on_dropdown")
    async def automations_select_listener(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "AutomacoesSelect":
            selected_value = inter.values[0]
            mode = db.get_document("custom_mode").get("mode")

            # Itens em breve: responder com mensagem efêmera e não navegar
            coming_soon = {
                "autorole", "temp_em_call",
                "formularios", "parcerias", "gifts", "instagram", "cartas"
            }
            if selected_value in coming_soon:
                await inter.response.send_message(
                    "Essa funcionalidade será implementada em breve em próximas atualizações.",
                    ephemeral=True
                )
                return

            if mode == "embed":
                await embed_message.wait(inter, send=False)
            else:
                await message.wait(inter, send=False)

            if selected_value == "regras_negocio":
                rules_cog = self.bot.get_cog("BusinessRulesConfigCog")
                if rules_cog:
                    if mode == "embed":
                        embed, components = rules_cog.panel_embed()
                        await inter.edit_original_message(content=None, embed=embed, components=components)
                    else:
                        await inter.edit_original_message(components=rules_cog.panel_components())
                return

            # Handle ia_chat with embed support
            if selected_value == "ia_chat":
                if mode == "embed":
                    embed, components = AIChatCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
                # Fall-through for component mode
            
            if selected_value == "filtro_tos":
                if mode == "embed":
                    embed, components = AIModeratorCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "boasvindas":
                if mode == "embed":
                    embed, components = BoasVindasConfig.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "limpeza_canais":
                if mode == "embed":
                    embed, components = CleanCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return

            if selected_value == "contador_membros":
                if mode == "embed":
                    embed, components = ContMembrosCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return

            if selected_value == "contador_membros_call":
                if mode == "embed":
                    embed, components = ContMembrosCallCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return

            if selected_value == "contador_vends":
                if mode == "embed":
                    embed, components = ContVendasCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return

            if selected_value == "feedbacks":
                if mode == "embed":
                    embed, components = FeedbacksCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return

            if selected_value == "formularios":
                if mode == "embed":
                    embed, components = FormsCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return

            if selected_value == "invite_tracker":
                if mode == "embed":
                    embed, components = InviteTrackerCog.PainelEmbed(self.bot)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "lock_unlock_canais":  
                if mode == "embed":
                    embed, components = LockUnlockCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "nuke":
                if mode == "embed":
                    embed, components = NukeCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "reacoes": 
                if mode == "embed":
                    embed, components = ReacoesCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "respostas_auto":
                if mode == "embed":
                    embed, components = RespAutomaticasCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "sugestoes":
                if mode == "embed":
                    embed, components = SuggestionsCog.PainelEmbed(self.bot, inter.guild)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "repostagem":
                if mode == "embed":
                    embed, components = RepostCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            if selected_value == "topicos":
                if mode == "embed":
                    embed, components = TopicsCog.PainelEmbed(self.bot, inter.guild)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return  

            if selected_value == "formularios":
                if mode == "embed":
                    embed, components = FormsCog.PainelEmbed()
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                    return
            
            # Define the target panel based on selection
            target_panel = None
            if selected_value == "boasvindas":
                target_panel = BoasVindasConfig.Painel()
            elif selected_value == "contador_membros":
                target_panel = ContMembrosCog.Painel()
            elif selected_value == "filtro_tos":
                target_panel = AIModeratorCog.Painel()
            elif selected_value == "ia_chat":
                target_panel = AIChatCog.Painel()
            elif selected_value == "limpeza_canais":
                target_panel = CleanCog.Painel()
            elif selected_value == "feedbacks":
                target_panel = FeedbacksCog.Painel()
            elif selected_value == "formularios":
                target_panel = FormsCog.Painel()
            elif selected_value == "contador_membros_call":
                target_panel = ContMembrosCallCog.Painel()
            elif selected_value == "contador_vends":
                target_panel = ContVendasCog.Painel()
            elif selected_value == "invite_tracker":
                target_panel = InviteTrackerCog.Painel(self.bot)
            elif selected_value == "lock_unlock_canais":
                target_panel = LockUnlockCog.Painel()
            elif selected_value == "nuke":
                target_panel = NukeCog.Painel()
            elif selected_value == "mensagens_auto":
                target_panel = MsgAutoCog.Painel()
            elif selected_value == "reacoes":
                reactions_db = ReacoesDB()
                ui = ReacoesUI(self.bot, reactions_db)
                target_panel = ui.Painel()
            elif selected_value == "respostas_auto":
                response_auto_db = RespAutomaticasDB()
                ui = RespAutomaticasUI(response_auto_db)
                target_panel = ui.Painel()
            elif selected_value == "sugestoes":
                ui = SuggestionsUI(self.bot)
                target_panel = ui.Painel(inter.guild)
            elif selected_value == "topicos":
                ui = TopicsCog(self.bot)
                target_panel = ui.Painel(inter.guild)
            elif selected_value == "repostagem":
                target_panel = RepostCog.Painel()

            if mode == "embed" and selected_value == "mensagens_auto":
                await inter.delete_original_message()
                await inter.followup.send(components=target_panel, ephemeral=True)
            elif target_panel:
                await inter.edit_original_message(content=None, components=target_panel)
            else:
                # Fallback for unimplemented options in component mode
                comps = AutomationModulesCog.PainelComponents()
                error_message = disnake.ui.TextDisplay("Esta automação ainda não foi configurada.")
                comps.insert(0, error_message)
                await inter.edit_original_message(content=None, components=comps)

def setup(bot: commands.Bot):
    bot.add_cog(AutomationModulesCog(bot))
