import disnake
from disnake.ext import commands
from functions.emoji import emoji
from functions.message import message
from . import helpers
from commands.admin.anunciar.builder import Builder
from commands.admin.anunciar.components.helper import Helper as AnunciarHelper
import uuid
import re
import time
from functions.database import database as db
from functions.utils import utils

# region Modals
class ConfigurarIntervaloModal(disnake.ui.Modal):
    def __init__(self, canal_id: str):
        self.canal_id = canal_id
        super().__init__(
            title="Configurar Mensagem Automática",
            custom_id=f"MsgAuto_ConfigIntervaloModal:{self.canal_id}",
            components=[
                disnake.ui.TextInput(
                    label="Intervalo em minutos (mínimo 1)",
                    placeholder="Ex: 60 (para 1 hora), 1440 (para 24h)",
                    custom_id="intervalo",
                    style=disnake.TextInputStyle.short,
                    required=True, min_length=1, max_length=5
                )
            ],
        )

class DefinirMensagemModal(disnake.ui.Modal):
    def __init__(self, msg_id: str):
        self.msg_id = msg_id
        editor_data = helpers.get_editor_data(msg_id)
        # Discord limit: custom_id must be between 1 and 100 characters
        custom_id = f"MsgAuto_DefinirMensagemModal:{msg_id}"
        if len(custom_id) > 100:
            custom_id = custom_id[:97] + "..."
        super().__init__(
            title="Definir Mensagem",
            custom_id=custom_id,
            components=[
                disnake.ui.TextInput(
                    label="Mensagem", custom_id="message", style=disnake.TextInputStyle.paragraph,
                    placeholder="Digite a mensagem que deseja anunciar", value=editor_data.get("content", ""),
                    max_length=2000, required=True
                )
            ],
        )

class DefinirEmbedModal(disnake.ui.Modal):
    def __init__(self, msg_id: str):
        self.msg_id = msg_id
        editor_data = helpers.get_editor_data(msg_id)
        embed_data = editor_data.get("embed", {})
        # Discord limit: custom_id must be between 1 and 100 characters
        custom_id = f"MsgAuto_DefinirEmbedModal:{msg_id}"
        if len(custom_id) > 100:
            custom_id = custom_id[:97] + "..."
        super().__init__(
            title="Definir Embed",
            custom_id=custom_id,
            components=[
                disnake.ui.TextInput(label="Título", custom_id="embed_title", style=disnake.TextInputStyle.short, required=False, value=embed_data.get("title", "")),
                disnake.ui.TextInput(label="Descrição", custom_id="embed_description", style=disnake.TextInputStyle.paragraph, placeholder="Descrição do embed aqui", required=True, value=embed_data.get("description", "")),
                disnake.ui.TextInput(label="Cor (Hex)", custom_id="embed_color", style=disnake.TextInputStyle.short, required=False, placeholder="#FFFFFF", value=embed_data.get("color", "")),
                disnake.ui.TextInput(label="Footer", custom_id="embed_footer", style=disnake.TextInputStyle.short, required=False, value=embed_data.get("footer", "")),
            ]
        )

class DefinirImagensModal(disnake.ui.Modal):
    def __init__(self, msg_id: str):
        self.msg_id = msg_id
        editor_data = helpers.get_editor_data(msg_id)
        embed_data = editor_data.get("embed", {})
        has_embed = bool(embed_data.get("title") or embed_data.get("description"))

        components = [
            disnake.ui.TextInput(label="URL da imagem externa", custom_id="externalImage", style=disnake.TextInputStyle.short, required=False, value=editor_data.get("externalImage", "")),
        ]

        if has_embed:
            components.extend([
                disnake.ui.TextInput(label="URL do Banner do Embed", custom_id="banner", style=disnake.TextInputStyle.short, required=False, value=embed_data.get("banner", "")),
                disnake.ui.TextInput(label="URL da Thumbnail do Embed", custom_id="thumbnail", style=disnake.TextInputStyle.short, required=False, value=embed_data.get("thumbnail", "")),
            ])
        
        # Discord limit: custom_id must be between 1 and 100 characters
        custom_id = f"MsgAuto_DefinirImagensModal:{msg_id}"
        if len(custom_id) > 100:
            custom_id = custom_id[:97] + "..."
        super().__init__(title="Definir Imagens", custom_id=custom_id, components=components)

class DefinirContainerModal(disnake.ui.Modal):
    def __init__(self, msg_id: str):
        self.msg_id = msg_id
        editor_data = helpers.get_editor_data(msg_id)
        
        # Discord limit: custom_id must be between 1 and 100 characters
        custom_id = f"MsgAuto_DefinirContainerModal:{msg_id}"
        if len(custom_id) > 100:
            custom_id = custom_id[:97] + "..."
        super().__init__(
            title="Definir Container",
            custom_id=custom_id,
            components=[
                disnake.ui.TextInput(
                    label="Conteúdo do container", style=disnake.TextInputStyle.paragraph, 
                    custom_id="container_content", placeholder="Use {{separator}}, {{color:#...}}, {{image url=...}}", 
                    required=True, value=editor_data.get("container", "")
                ),
            ]
        )

class DefinirBotoesModal(disnake.ui.Modal):
    def __init__(self, msg_id: str):
        self.msg_id = msg_id
        # Discord limit: custom_id must be between 1 and 100 characters
        custom_id = f"MsgAuto_DefinirBotoesModal:{msg_id}"
        if len(custom_id) > 100:
            custom_id = custom_id[:97] + "..."
        super().__init__(
            title="Definir Botão",
            custom_id=custom_id,
            components=[
                disnake.ui.TextInput(label="Label", custom_id="button_label", required=True, max_length=30),
                disnake.ui.TextInput(label="URL (Opcional)", custom_id="button_url", placeholder="Deixe em branco para um botão de ação", required=False),
                disnake.ui.TextInput(label="Emoji (Opcional)", custom_id="button_emoji", required=False),
            ]
        )
    
    async def callback(self, inter: disnake.ModalInteraction):
        # A lógica será tratada no on_modal_submit para gerenciar o fluxo de ação
        return None

class ModalEphemeralMessage(disnake.ui.Modal):
    def __init__(self, msg_id: str):
        self.msg_id = msg_id
        # Discord limit: custom_id must be between 1 and 100 characters
        custom_id = f"MsgAuto_ModalEphMsg:{msg_id}"
        if len(custom_id) > 100:
            custom_id = custom_id[:97] + "..."
        super().__init__(
            title="Mensagem Efêmera",
            custom_id=custom_id,
            components=[
                disnake.ui.TextInput(label="Conteúdo da Mensagem", custom_id="ephemeral_message_content", style=disnake.TextInputStyle.paragraph, required=True, max_length=2000)
            ]
        )

class EditarConfigModal(disnake.ui.Modal):
    def __init__(self, msg_id: str):
        self.msg_id = msg_id
        msg_config = helpers.get_message_config(msg_id)
        # Discord limit: custom_id must be between 1 and 100 characters
        custom_id = f"MsgAuto_EditarConfigModal:{msg_id}"
        if len(custom_id) > 100:
            custom_id = custom_id[:97] + "..."
        super().__init__(
            title="Editar Configurações",
            custom_id=custom_id,
            components=[
                disnake.ui.TextInput(label="Intervalo em minutos", custom_id="intervalo", value=str(msg_config.get("intervalo_minutos", 60)), required=True, min_length=1, max_length=7),
            ]
        )

# endregion


class MsgAutoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    class ButtonManager:
        """
        Classe adaptada de commands/admin/anunciar/components/buttons.py
        para gerenciar a UI de botões para o sistema de mensagens automáticas.
        """
        
        description_names = {
            "disabled": "Botão desabilitado", "action": "Botão de ação (cargos)",
            "message": "Botão de mensagem efêmera", "url": "Botão de URL",
        }
        
        @staticmethod
        def _get_cfg(msg_id: str):
            return helpers.get_editor_data(msg_id)

        @staticmethod
        def _save_cfg(msg_id: str, cfg: dict):
            helpers.set_editor_data(msg_id, cfg)

        @staticmethod
        def _find_button(cfg: dict, button_id: str):
            buttons = cfg.get("botoes", [])
            return next((b for b in buttons if b.get("id") == button_id), None)

        @staticmethod
        def _style_from_str(style: str) -> disnake.ButtonStyle:
            STYLE_MAPPING = {
                "gray": disnake.ButtonStyle.gray, "grey": disnake.ButtonStyle.gray, "green": disnake.ButtonStyle.green,
                "red": disnake.ButtonStyle.red, "blue": disnake.ButtonStyle.blurple, "url": disnake.ButtonStyle.url,
            }
            return STYLE_MAPPING.get(style or "gray", disnake.ButtonStyle.gray)
        
        @staticmethod
        def _is_valid_url(url: str) -> bool:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"): return False
                if not parsed.netloc or " " in parsed.netloc: return False
                if "." not in parsed.netloc: return False
                return True
            except Exception:
                return False

        @staticmethod
        def validar_emoji(emoji_input: str, bot: commands.Bot) -> bool:
            if not emoji_input or emoji_input.strip() == "": return True
            emoji_input = emoji_input.strip()
            DISCORD_EMOJI_RE = re.compile(r"<a?:[a-zA-Z0-9_]{2,32}:\d{17,22}>")
            UNICODE_EMOJI_RE = re.compile(
                "[" "\U0001F600-\U0001F64F" "\U0001F300-\U0001F5FF" "\U0001F680-\U0001F6FF"
                "\U0001F1E0-\U0001F1FF" "\U0001F900-\U0001F9FF" "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251" "]+",
                flags=re.UNICODE,
            )
            if hasattr(emoji, emoji_input):
                value = getattr(emoji, emoji_input)
                if isinstance(value, str) and DISCORD_EMOJI_RE.fullmatch(value):
                    try: 
                        pe = disnake.PartialEmoji.from_str(value)
                        return bool(pe and pe.id)
                    except Exception: 
                        return False
                return True
            if DISCORD_EMOJI_RE.fullmatch(emoji_input):
                try: 
                    pe = disnake.PartialEmoji.from_str(emoji_input)
                    return bool(pe and pe.id)
                except Exception: 
                    return False
            if UNICODE_EMOJI_RE.fullmatch(emoji_input):
                return True
            return False

        @staticmethod
        def processar_emoji(emoji_input: str):
            if not emoji_input or emoji_input.strip() == "": return None
            emoji_input = emoji_input.strip()
            DISCORD_EMOJI_RE = re.compile(r"<a?:[a-zA-Z0-9_]{2,32}:\d{17,22}>")
            UNICODE_EMOJI_RE = re.compile(
                "[" "\U0001F600-\U0001F64F" "\U0001F300-\U0001F5FF" "\U0001F680-\U0001F6FF"
                "\U0001F1E0-\U0001F1FF" "\U0001F900-\U0001F9FF" "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251" "]+",
                flags=re.UNICODE,
            )
            
            # Handle shortnames from functions.emoji
            if hasattr(emoji, emoji_input):
                emoji_input = getattr(emoji, emoji_input)
            
            if DISCORD_EMOJI_RE.fullmatch(emoji_input):
                try: 
                    return disnake.PartialEmoji.from_str(emoji_input)
                except Exception: 
                    return None
            if UNICODE_EMOJI_RE.fullmatch(emoji_input):
                return emoji_input
            return None

        class RegistrarBotao(disnake.ui.Modal):
            def __init__(self, msg_id: str, action: str, button_id: str = None):
                self.msg_id = msg_id
                self.action = action
                self.button_id = button_id
                cfg = MsgAutoCog.ButtonManager._get_cfg(msg_id)
                button = MsgAutoCog.ButtonManager._find_button(cfg, button_id) if button_id else None

                super().__init__(
                    title="Registrar botão",
                    custom_id=f"MA_BtnModal_RegBtn:{msg_id}:{action}:{button_id or ''}",
                    components=[
                        disnake.ui.TextInput(label="Label", custom_id="label", placeholder="Label do botão", required=True, value=button.get("label", "") if button else ""),
                        disnake.ui.TextInput(label="Emoji", custom_id="emoji", placeholder="Emoji do botão (opcional)", required=False, value=button.get("button", {}).get("emoji", "") if button else ""),
                    ]
                )

        class EditarURLModal(disnake.ui.Modal):
            def __init__(self, msg_id: str, button_id: str):
                self.msg_id = msg_id
                self.button_id = button_id
                cfg = MsgAutoCog.ButtonManager._get_cfg(msg_id)
                button = MsgAutoCog.ButtonManager._find_button(cfg, button_id)
                url_value = (button or {}).get("button", {}).get("url") if button else None

                super().__init__(
                    title="Editar URL",
                    custom_id=f"MA_BtnModal_EditURL:{msg_id}:{button_id}",
                    components=[
                        disnake.ui.TextInput(label="URL", custom_id="url", placeholder="https://exemplo.com", required=True, value=url_value or "")
                    ]
                )

        class EditarMensagemModal(disnake.ui.Modal):
            def __init__(self, msg_id: str, button_id: str):
                self.msg_id = msg_id
                self.button_id = button_id
                cfg = MsgAutoCog.ButtonManager._get_cfg(msg_id)
                button = MsgAutoCog.ButtonManager._find_button(cfg, button_id)
                msg_value = ((button or {}).get("button", {}).get("action", {}) or {}).get("message") if button else None

                super().__init__(
                    title="Editar mensagem efêmera",
                    custom_id=f"MA_BtnModal_EditMsg:{msg_id}:{button_id}",
                    components=[
                        disnake.ui.TextInput(label="Mensagem", custom_id="message", placeholder="Texto da mensagem efêmera", required=True, value=msg_value or "", style=disnake.TextInputStyle.paragraph)
                    ]
                )

        @staticmethod
        def buttons_panel(msg_id: str):
            colors = db.get_document("custom_colors")
            primary_color_hex = colors.get("primary")
            container_kwargs = {}
            if primary_color_hex:
                primary_color = int(primary_color_hex.replace("#", ""), 16)
                container_kwargs["accent_colour"] = disnake.Colour(primary_color)
            cfg = MsgAutoCog.ButtonManager._get_cfg(msg_id)
            buttons = cfg.get("botoes", [])
            options = [
                disnake.SelectOption(
                    label=b.get("label", "Sem nome"), value=b.get("id"), emoji=emoji.plus,
                    description=MsgAutoCog.ButtonManager.description_names.get(b.get("button", {}).get("type", "disabled"), "Botão")
                ) for b in buttons
            ] or [disnake.SelectOption(label="Nenhum botão registrado", value="none", description="Nenhum botão registrado")]

            return [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Mensagens Automáticas > Botões"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(f"Configure os botões que irão aparecer na mensagem.\nPara configurar um botão, selecione-o na lista abaixo."),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(f"**Quantidade de botões registrados:** `{len(buttons)}`\n-# A quantidade de botões registrados é limitada a `5`."),
                    disnake.ui.ActionRow(
                        disnake.ui.StringSelect(
                            placeholder="Selecione o botão para configurar", custom_id=f"MsgAuto_Botao_SelecionarBotao:{msg_id}",
                            options=options, disabled=len(buttons) == 0
                        )
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(label="Adicionar botão", style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id=f"MsgAuto_Botao_AdicionarBotao:{msg_id}", disabled=len(buttons) == 5),
                        disnake.ui.Button(label="Apagar todos", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"MsgAuto_Botao_ApagarTodos:{msg_id}", disabled=len(buttons) == 0)
                    ),
                    **container_kwargs,
                ),
                disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id=f"MsgAuto_PainelEditor:{msg_id}")),
            ]

        class Button:
            @staticmethod
            def button_config_panel(msg_id: str, button_id: str):
                colors = db.get_document("custom_colors")
                primary_color_hex = colors.get("primary")
                container_kwargs = {}
                if primary_color_hex:
                    primary_color = int(primary_color_hex.replace("#", ""), 16)
                    container_kwargs["accent_colour"] = disnake.Colour(primary_color)
                cfg = MsgAutoCog.ButtonManager._get_cfg(msg_id)
                button = MsgAutoCog.ButtonManager._find_button(cfg, button_id)
                if not button: return None

                label = button.get("label", "Nenhum label")
                data = button.get("button", {})
                btn_type = data.get("type", "disabled")
                emoji_raw = data.get("emoji")
                emojiButton = MsgAutoCog.ButtonManager.processar_emoji(emoji_raw) if emoji_raw else None
                url = data.get("url")
                style = MsgAutoCog.ButtonManager._style_from_str(data.get("style"))
                style_str = data.get("style") or "gray"  # Usar string para comparação

                return [
                    disnake.ui.Container(
                        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Mensagens Automáticas > Botões > {button.get('label')}"),
                        disnake.ui.Separator(),
                        disnake.ui.Section(
                            disnake.ui.TextDisplay(f"**Label do botão:** `{label}`\n**Emoji do botão:** {emojiButton if emojiButton else '`Nenhum emoji`'}"),
                            accessory=disnake.ui.Button(label=label, emoji=emojiButton, disabled=True, style=style, url=url)
                        ),
                        disnake.ui.Separator(),
                        disnake.ui.TextDisplay(f"**Tipo do botão:** `{MsgAutoCog.ButtonManager.description_names.get(btn_type, 'Botão desabilitado')}`"),
                        disnake.ui.ActionRow(
                            disnake.ui.StringSelect(
                                placeholder="Selecione o estilo do botão",
                                custom_id=f"MA_Btn_Style:{msg_id}:{button_id}",
                                options=[
                                    disnake.SelectOption(label="Cinza", value="gray", emoji=emoji.gray, default=style_str == "gray" or style_str == "grey"),
                                    disnake.SelectOption(label="Verde", value="green", emoji=emoji.green, default=style_str == "green"),
                                    disnake.SelectOption(label="Vermelho", value="red", emoji=emoji.red, default=style_str == "red"),
                                    disnake.SelectOption(label="Azul", value="blue", emoji=emoji.blue, default=style_str == "blue"),
                                ]
                            )
                        ),
                        disnake.ui.ActionRow(
                            disnake.ui.Button(label="Editar botão", emoji=emoji.edit, custom_id=f"MA_Btn_EditBtn:{msg_id}:{button_id}", style=disnake.ButtonStyle.blurple),
                            disnake.ui.Button(label="Editar ações", emoji=emoji.route, custom_id=f"MA_Btn_EditAct:{msg_id}:{button_id}"),
                            disnake.ui.Button(label="Apagar botão", emoji=emoji.delete, custom_id=f"MA_Btn_DelBtn:{msg_id}:{button_id}", style=disnake.ButtonStyle.red)
                        ),
                        **container_kwargs,
                    ),
                    disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id=f"MsgAuto_DefinirBotoes:{msg_id}")),
                ]

            @staticmethod
            def acoes_panel(msg_id: str, button_id: str, inter: disnake.MessageInteraction):
                colors = db.get_document("custom_colors")
                primary_color_hex = colors.get("primary")
                container_kwargs = {}
                if primary_color_hex:
                    primary_color = int(primary_color_hex.replace("#", ""), 16)
                    container_kwargs["accent_colour"] = disnake.Colour(primary_color)
                cfg = MsgAutoCog.ButtonManager._get_cfg(msg_id)
                button = MsgAutoCog.ButtonManager._find_button(cfg, button_id)
                if not button: return None

                select_button = None
                data = button.get("button", {})
                current_type = data.get("type")
                action_data = data.get("action") or {}
                action_type = action_data.get("type")

                ACTION_DESCRIPTIONS = {
                    "addrole": "Adiciona/remove um cargo definido ao usuário.", "removerole": "Remove um cargo definido ao usuário.",
                    "message": "Envia uma mensagem efêmera.", "url": "Redireciona o usuário para uma URL.", "disabled": "Desabilita o botão.",
                }

                def action_select():
                    return disnake.ui.StringSelect(
                        custom_id=f"MA_Btn_ChgAct:{msg_id}:{button_id}",
                        placeholder="Selecione a ação para ativar",
                        options=[
                            disnake.SelectOption(label="Dar Cargo (Toggle)", emoji=emoji.plus, value="DarCargo", default=(current_type == "action" and action_type == "addrole"), description=ACTION_DESCRIPTIONS["addrole"]),
                            disnake.SelectOption(label="Remover Cargo", emoji=emoji.minus, value="RemoverCargo", default=(current_type == "action" and action_type == "removerole"), description=ACTION_DESCRIPTIONS["removerole"]),
                            disnake.SelectOption(label="Mensagem Efêmera", emoji=emoji.message, value="MensagemEferema", default=(current_type == "message"), description=ACTION_DESCRIPTIONS["message"]),
                            disnake.SelectOption(label="URL", emoji=emoji.route, value="URL", default=(current_type == "url"), description=ACTION_DESCRIPTIONS["url"]),
                            disnake.SelectOption(label="Desativado", emoji=emoji.wrong, value="Desativado", default=(current_type == "disabled"), description=ACTION_DESCRIPTIONS["disabled"]),
                        ]
                    )

                if current_type == "action":
                    if action_type == "addrole" or action_type == "removerole":
                        role_id = action_data.get("role")
                        role = inter.guild.get_role(int(role_id)) if role_id else None
                        select_button = disnake.ui.RoleSelect(
                            placeholder="Selecione o cargo para adicionar" if action_type == "addrole" else "Selecione o cargo para remover",
                            custom_id=f"MA_Btn_AddRole:{msg_id}:{button_id}" if action_type == "addrole" else f"MA_Btn_RemRole:{msg_id}:{button_id}",
                            default_values=[role] if role else []
                        )
                elif current_type == "url":
                    select_button = disnake.ui.Button(label="Editar URL", emoji=emoji.edit, custom_id=f"MA_Btn_EditURL:{msg_id}:{button_id}", style=disnake.ButtonStyle.blurple)
                elif current_type == "message":
                    select_button = disnake.ui.Button(label="Editar mensagem", emoji=emoji.edit, custom_id=f"MA_Btn_EditMsg:{msg_id}:{button_id}", style=disnake.ButtonStyle.blurple)
                elif current_type == "disabled":
                    select_button = disnake.ui.Button(label="Personalizar botão", emoji=emoji.edit, custom_id=f"MsgAuto_Botao_Dummy", style=disnake.ButtonStyle.blurple, disabled=True)

                components_list = [
                    disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Mensagens Automáticas > Botões > {button.get('label')} > Ações"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(f"Configure as ações que irão aparecer no botão.\nPara remover uma ação, desative o botão."),
                    disnake.ui.Separator(),
                ]

                if select_button:
                    components_list.append(disnake.ui.ActionRow(select_button))

                components_list.append(disnake.ui.ActionRow(action_select()))
                
                return [
                    disnake.ui.Container(*components_list, **container_kwargs),
                    disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id=f"MA_Btn_CfgBtn:{msg_id}:{button_id}")),
                ]

    @staticmethod
    def Painel() -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        config = helpers.carregar_config()
        ativado = bool(config.get("ativado", False))
        mensagens = config.get("mensagens", {})
        
        resumo = (
            f"{emoji.on if ativado else emoji.off} **Status:** `{'Ativado' if ativado else 'Desativado'}`\n"
            f"{emoji.message} **Mensagens configuradas:** `{len(mensagens)}`\n"
        )

        botoes_principais = [
            disnake.ui.Button(label="", style=disnake.ButtonStyle.grey, emoji=emoji.power, custom_id="MsgAuto_ToggleAtivo"),
            disnake.ui.Button(label="Adicionar", style=disnake.ButtonStyle.blurple, emoji=emoji.plus, custom_id="MsgAuto_Adicionar", disabled=not ativado)
        ]

        if mensagens:
            botoes_principais.append(
                disnake.ui.Button(label="Editar", style=disnake.ButtonStyle.gray, emoji=emoji.edit, custom_id="MsgAuto_Editar", disabled=not ativado)
            )

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Automações > **Mensagens Automáticas**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay("Configure as mensagens automáticas do servidor."),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(resumo),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(*botoes_principais),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="MsgAuto_VoltarAutomacoes"),
            )
        ]

    @staticmethod
    def PainelAdicionar() -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Automações > Mensagens Automáticas > **Adicionar**"),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.ChannelSelect(
                        placeholder="Selecione um canal...",
                        custom_id="MsgAuto_SelectCanal",
                        min_values=1, max_values=1,
                        channel_types=[disnake.ChannelType.text]
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="MsgAuto_VoltarPainel"),
            )
        ]

    @staticmethod
    def PainelSelecionarEditar(bot: commands.Bot):
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        config = helpers.carregar_config()
        mensagens = config.get("mensagens", {})
        
        if not mensagens:
            return [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {emoji.edit} Nenhuma mensagem automática configurada."),
                    disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", custom_id="MsgAuto_VoltarPainel")),
                    **container_kwargs,
                )
            ]

        options = []
        for msg_id, data in mensagens.items():
            intervalo = data.get('intervalo_minutos', 'N/A')
            canal_id = data.get('channel_id')
            
            ch_info = f"ID do Canal: {canal_id}"
            if canal_id:
                try:
                    ch = bot.get_channel(int(canal_id))
                    ch_info = f"Canal: #{ch.name}" if ch else "Canal não encontrado"
                except (ValueError, TypeError):
                    ch_info = "ID de canal inválido"
            else:
                ch_info = "Nenhum canal definido"

            label = f"{ch_info} ({intervalo}m)"
            desc = f"ID da Mensagem: {msg_id}"
            options.append(disnake.SelectOption(label=label, value=msg_id, description=desc))
            
        if not options:
            options.append(disnake.SelectOption(label="Nenhuma mensagem para editar", value="ignore"))

        select = disnake.ui.StringSelect(
            custom_id="MsgAuto_SelecionarParaEditar",
            placeholder="Selecione uma mensagem para editar",
            options=options,
        )

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Automações > Mensagens Automáticas > **Editar**"),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(select),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="MsgAuto_VoltarPainel"),
            ),
        ]

    @staticmethod
    def PainelEditor(bot: commands.Bot, msg_id: str) -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        msg_config = helpers.get_message_config(msg_id)
        editor_data = msg_config.get("editor_data", {})
        
        info_texto = f"{emoji.textc} **Canal:** <#{msg_config.get('channel_id')}>\n{emoji.time} **Intervalo:** `{msg_config.get('intervalo_minutos')} minutos`"
        has_message = bool(editor_data.get("content"))
        embed_data = editor_data.get("embed", {})
        has_embed = any(embed_data.get(k) for k in ("title", "description", "footer"))
        has_image = bool(editor_data.get("externalImage") or embed_data.get("banner") or embed_data.get("thumbnail"))
        has_container = bool(editor_data.get("container"))
        botoes = editor_data.get("botoes", [])
        has_buttons = isinstance(botoes, list) and len(botoes) > 0
        limite_botoes = isinstance(botoes, list) and len(botoes) >= 5

        # Desabilita outros campos se um container estiver ativo
        other_fields_disabled = has_container

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Automações > Mensagens Automáticas > **Editor**"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(info_texto),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"MsgAuto_ApagarCampo:content:{msg_id}", disabled=not has_message or other_fields_disabled),
                    disnake.ui.Button(label="Definir Mensagem", style=disnake.ButtonStyle.grey, emoji=emoji.message, custom_id=f"MsgAuto_DefinirMensagem:{msg_id}", disabled=other_fields_disabled),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"MsgAuto_ApagarCampo:embed:{msg_id}", disabled=not has_embed or other_fields_disabled),
                    disnake.ui.Button(label="Definir Embed", style=disnake.ButtonStyle.grey, emoji=emoji.embed, custom_id=f"MsgAuto_DefinirEmbed:{msg_id}", disabled=other_fields_disabled),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"MsgAuto_ApagarImagensMulti:{msg_id}", disabled=not has_image),
                    disnake.ui.Button(label="Definir Imagens", style=disnake.ButtonStyle.grey, emoji=emoji.image, custom_id=f"MsgAuto_DefinirImagens:{msg_id}"),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"MsgAuto_ApagarCampo:container:{msg_id}", disabled=not has_container),
                    disnake.ui.Button(label="Definir Container", style=disnake.ButtonStyle.grey, emoji=emoji.commands, custom_id=f"MsgAuto_DefinirContainer:{msg_id}", disabled=(has_message or has_embed) and not has_container),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"MsgAuto_ApagarCampo:botoes:{msg_id}", disabled=not has_buttons),
                    disnake.ui.Button(label="Adicionar Botão", style=disnake.ButtonStyle.grey, emoji=emoji.plus, custom_id=f"MsgAuto_DefinirBotoes:{msg_id}", disabled=limite_botoes),
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Visualizar", style=disnake.ButtonStyle.grey, emoji=emoji.search, custom_id=f"MsgAuto_Visualizar:{msg_id}", disabled=not (has_message or has_embed or has_container or has_image or has_buttons)),
                disnake.ui.Button(label="Apagar Mensagem", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"MsgAuto_ApagarMsg:{msg_id}"),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="MsgAuto_VoltarPainel"),
                disnake.ui.Button(label="Editar Configs", style=disnake.ButtonStyle.blurple, emoji=emoji.edit, custom_id=f"MsgAuto_EditarConfig:{msg_id}"),
            )
        ]

    @staticmethod
    def PainelActionSelect(msg_id: str):
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        cid = lambda name: f"{name}:{msg_id}"
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Editor > **Configurar Ação do Botão**"),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Adicionar/Remover Cargo", style=disnake.ButtonStyle.secondary, emoji=emoji.plus, custom_id=cid("MsgAuto_Action_ToggleRole")),
                    disnake.ui.Button(label="Remover Cargo", style=disnake.ButtonStyle.secondary, emoji=emoji.minus, custom_id=cid("MsgAuto_Action_RemoveRole")),
                    disnake.ui.Button(label="Mensagem Efêmera", style=disnake.ButtonStyle.secondary, emoji=emoji.message, custom_id=cid("MsgAuto_Action_EphemeralMessage")),
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Cancelar", style=disnake.ButtonStyle.red, emoji=emoji.wrong, custom_id=cid("MsgAuto_Action_Cancel")))
        ]
    
    @staticmethod
    def PainelRoleSelect(msg_id: str, action_type: str):
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        custom_id = f"MsgAuto_SelectRole:{action_type}:{msg_id}"
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Editor > Ação > **Selecionar Cargo**"),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.RoleSelect(placeholder="Selecione um cargo...", custom_id=custom_id, min_values=1, max_values=1)
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Cancelar", style=disnake.ButtonStyle.red, emoji=emoji.wrong, custom_id=f"MsgAuto_Action_Cancel:{msg_id}"))
        ]

    @staticmethod
    def PainelEditarConfig(bot: commands.Bot, msg_id: str):
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        msg_config = helpers.get_message_config(msg_id)
        channel_id = msg_config.get("channel_id")
        intervalo = msg_config.get("intervalo_minutos", 60)
        
        # Obter o canal atual para default_values, se existir
        default_channel = None
        if channel_id:
            try:
                default_channel = bot.get_channel(int(channel_id))
            except (ValueError, TypeError):
                pass
        
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Automações > Mensagens Automáticas > **Editar Configurações**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(f"{emoji.textc} **Canal atual:** <#{channel_id}>\n{emoji.time} **Intervalo atual:** `{intervalo} minutos`"),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.ChannelSelect(
                        placeholder="Selecione um novo canal...",
                        custom_id=f"MsgAuto_EditarConfig_Canal:{msg_id}",
                        min_values=1, max_values=1,
                        channel_types=[disnake.ChannelType.text],
                        default_values=[default_channel] if default_channel else []
                    )
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Editar Intervalo", style=disnake.ButtonStyle.blurple, emoji=emoji.time, custom_id=f"MsgAuto_EditarConfig_Intervalo:{msg_id}")
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"MsgAuto_PainelEditor:{msg_id}")
            )
        ]

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        cid = inter.component.custom_id
        if not (cid.startswith("MsgAuto_") or cid.startswith("MA_") or cid.startswith("Anunciar_RuntimeAction_Botao_")): 
            return

        if cid == "MsgAuto_VoltarAutomacoes":
            from modules.automations.cog import AutomationModulesCog
            await inter.response.defer(ephemeral=True)
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                embed, components = AutomationModulesCog.PainelEmbed()
                await inter.delete_original_message()
                await inter.followup.send(embed=embed, components=components, ephemeral=True)
            else:
                from functions.message import message
                await message.wait(inter, send=False)
                components = AutomationModulesCog.PainelComponents()
                await inter.delete_original_message()
                await inter.followup.send(components=components, ephemeral=True)
            return

        # Lógicas de botões
        if cid == "MsgAuto_ToggleAtivo":
            await inter.response.defer()
            config = helpers.carregar_config()
            config["ativado"] = not config.get("ativado", False)
            helpers.salvar_config(config)
            await inter.edit_original_message(components=self.Painel())

        elif cid == "MsgAuto_Adicionar":
            await inter.response.edit_message(components=self.PainelAdicionar())

        elif cid == "MsgAuto_Editar":
            await inter.response.defer()
            await inter.edit_original_message(components=self.PainelSelecionarEditar(self.bot))

        elif cid == "MsgAuto_VoltarPainel":
            await inter.response.defer()
            await inter.edit_original_message(components=self.Painel())

        elif cid.startswith("MsgAuto_ApagarMsg:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            helpers.delete_message(msg_id)
            await inter.edit_original_message(components=self.Painel())
            
        elif cid.startswith("MsgAuto_DefinirMensagem:"):
            msg_id = cid.split(":", 1)[1]
            await inter.response.send_modal(DefinirMensagemModal(msg_id))

        elif cid.startswith("MsgAuto_DefinirEmbed:"):
            msg_id = cid.split(":", 1)[1]
            await inter.response.send_modal(DefinirEmbedModal(msg_id))
            
        elif cid.startswith("MsgAuto_DefinirImagens:"):
            msg_id = cid.split(":", 1)[1]
            await inter.response.send_modal(DefinirImagensModal(msg_id))

        elif cid.startswith("MsgAuto_DefinirContainer:"):
            msg_id = cid.split(":", 1)[1]
            await inter.response.send_modal(DefinirContainerModal(msg_id))

        elif cid.startswith("MsgAuto_DefinirBotoes:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            await inter.edit_original_message(components=self.ButtonManager.buttons_panel(msg_id))
            
        elif cid.startswith("MsgAuto_Botao_AdicionarBotao:"):
            msg_id = cid.split(":", 1)[1]
            modal = self.ButtonManager.RegistrarBotao(msg_id=msg_id, action="create")
            await inter.response.send_modal(modal)
            
        elif cid.startswith("MsgAuto_Botao_ApagarTodos:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            cfg = self.ButtonManager._get_cfg(msg_id)
            cfg["botoes"] = []
            self.ButtonManager._save_cfg(msg_id, cfg)
            await inter.edit_original_message(components=self.ButtonManager.buttons_panel(msg_id))

        elif cid.startswith("MA_Btn_EditBtn:"):
            _, msg_id, button_id = cid.split(":")
            modal = self.ButtonManager.RegistrarBotao(msg_id=msg_id, action="edit", button_id=button_id)
            await inter.response.send_modal(modal)
            
        elif cid.startswith("MA_Btn_DelBtn:"):
            await inter.response.defer()
            _, msg_id, button_id = cid.split(":")
            cfg = self.ButtonManager._get_cfg(msg_id)
            button = self.ButtonManager._find_button(cfg, button_id)
            if button:
                cfg.setdefault("botoes", []).remove(button)
                self.ButtonManager._save_cfg(msg_id, cfg)
            await inter.edit_original_message(components=self.ButtonManager.buttons_panel(msg_id))

        elif cid.startswith("MA_Btn_EditAct:"):
            await inter.response.defer()
            _, msg_id, button_id = cid.split(":")
            button = self.ButtonManager._find_button(self.ButtonManager._get_cfg(msg_id), button_id)
            if not button: return
            await inter.edit_original_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))

        elif cid.startswith("MA_Btn_CfgBtn:"):
            await inter.response.defer()
            _, msg_id, button_id = cid.split(":")
            button = self.ButtonManager._find_button(self.ButtonManager._get_cfg(msg_id), button_id)
            if not button: return
            await inter.edit_original_message(components=self.ButtonManager.Button.button_config_panel(msg_id, button_id))

        elif cid.startswith("MA_Btn_EditURL:"):
            _, msg_id, button_id = cid.split(":")
            await inter.response.send_modal(self.ButtonManager.EditarURLModal(msg_id, button_id))

        elif cid.startswith("MA_Btn_EditMsg:"):
            _, msg_id, button_id = cid.split(":")
            await inter.response.send_modal(self.ButtonManager.EditarMensagemModal(msg_id, button_id))

        elif cid.startswith("MsgAuto_PainelEditor:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            await inter.edit_original_message(components=self.PainelEditor(self.bot, msg_id))

        elif cid.startswith("MsgAuto_ApagarCampo:"):
            await inter.response.defer()
            _, field, msg_id = cid.split(":", 2)
            helpers.clear_editor_field(msg_id, field)
            await inter.edit_original_message(components=self.PainelEditor(self.bot, msg_id))
        
        elif cid.startswith("MsgAuto_ApagarImagensMulti:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            editor_data = helpers.get_editor_data(msg_id)
            editor_data["externalImage"] = None
            if "embed" in editor_data:
                editor_data["embed"]["banner"] = None
                editor_data["embed"]["thumbnail"] = None
            helpers.set_editor_data(msg_id, editor_data)
            await inter.edit_original_message(components=self.PainelEditor(self.bot, msg_id))
        
        elif cid.startswith("MsgAuto_Visualizar:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            editor_data = helpers.get_editor_data(msg_id)
            if not any(editor_data.get(k) for k in ["content", "embed", "container", "externalImage", "botoes"]):
                await inter.followup.send("Não há nada para visualizar.", ephemeral=True)
                return
            
            data_to_build = editor_data.copy()
            if "botoes" in data_to_build and data_to_build["botoes"]:
                data_to_build["buttons"] = data_to_build.pop("botoes")
            else:
                data_to_build["buttons"] = [{
                    "id": "sync_auto_msg_disabled",
                    "label": "Mensagem Automática",
                    "button": {"type": "disabled", "style": "gray"}
                }]
            
            built = await self.bot.loop.run_in_executor(None, Builder.build_from_cfg, {"message": data_to_build})
            
            await self._send_built_message(inter, built, ephemeral=True)

        elif cid.startswith("MsgAuto_EditarConfig:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            await inter.edit_original_message(components=self.PainelEditarConfig(self.bot, msg_id))
        
        elif cid.startswith("MsgAuto_EditarConfig_Intervalo:"):
            msg_id = cid.split(":", 1)[1]
            await inter.response.send_modal(EditarConfigModal(msg_id))

        # Action Button Flow
        elif cid.startswith("MsgAuto_Action_Cancel:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            helpers.clear_editor_field(msg_id, "temp_action_button")
            await inter.edit_original_message(components=self.PainelEditor(self.bot, msg_id))
        
        elif cid.startswith("MsgAuto_Action_ToggleRole:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            await inter.edit_original_message(components=self.PainelRoleSelect(msg_id, "toggle_role"))

        elif cid.startswith("MsgAuto_Action_RemoveRole:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            await inter.edit_original_message(components=self.PainelRoleSelect(msg_id, "remove_role"))

        elif cid.startswith("MsgAuto_Action_EphemeralMessage:"):
            msg_id = cid.split(":", 1)[1]
            await inter.response.send_modal(ModalEphemeralMessage(msg_id))

        elif cid.startswith("Anunciar_RuntimeAction_Botao_"):
            button_data = helpers.find_button_by_custom_id(cid)

            if not button_data:
                # Verifica se é um botão do sistema anunciar antes de dar erro
                from commands.admin.anunciar.components.buttons import Buttons
                from functions.database import database
                cfg = database.get_document("messages_anunciar")
                anunciar_button = Buttons._find_button(cfg, cid.replace("Anunciar_RuntimeAction_Botao_", ""))
                if anunciar_button:
                    return  # Deixa o handler do anunciar processar
                await inter.response.send_message(f"{emoji.warn} Este botão não está mais funcionando.", ephemeral=True)
                return

            data = button_data.setdefault("button", {})
            btn_type = data.get("type")
            action = data.get("action") or {}

            if btn_type == "message":
                text = (action or {}).get("message") or "Mensagem não configurada."
                try:
                    # Para mensagens grandes (>1000 chars), sempre usar defer + followup
                    # Isso evita timeout e dá mais tempo ao Discord processar
                    if len(text) > 1000:
                        if not inter.response.is_done():
                            await inter.response.defer(ephemeral=True)
                        await inter.followup.send(text, ephemeral=True)
                    else:
                        # Para mensagens pequenas, tentar método direto primeiro
                        if inter.response.is_done():
                            await inter.followup.send(text, ephemeral=True)
                        else:
                            await inter.response.send_message(text, ephemeral=True)
                except disnake.HTTPException as e:
                    # Se houver erro, usar defer + followup como fallback
                    if getattr(e, "code", None) == 40060 or "Interaction has already been acknowledged" in str(e):
                        await inter.followup.send(text, ephemeral=True)
                    else:
                        # Para outros erros, tentar defer + followup
                        try:
                            if not inter.response.is_done():
                                await inter.response.defer(ephemeral=True)
                            await inter.followup.send(text, ephemeral=True)
                        except Exception:
                            await inter.followup.send(f"{emoji.warn} Erro ao enviar mensagem. Tente novamente.", ephemeral=True)
                return

            if btn_type == "action":
                action_type = action.get("type")
                role_id = action.get("role")
                if not role_id:
                    await inter.response.send_message(f"{emoji.warn} Nenhuma ação de cargo foi configurada para este botão.", ephemeral=True)
                    return
                
                role = inter.guild.get_role(int(role_id))
                if not role:
                    await inter.response.send_message(f"{emoji.warn} O cargo configurado não foi encontrado.", ephemeral=True)
                    return

                member: disnake.Member = inter.user
                me: disnake.Member = inter.guild.me

                if not me.guild_permissions.manage_roles:
                    await inter.response.send_message(f"{emoji.wrong} Eu não tenho permissão para gerenciar cargos.", ephemeral=True)
                    return
                if role >= me.top_role:
                    await inter.response.send_message(f"{emoji.wrong} O cargo `{role.name}` está acima do meu cargo no servidor, não consigo gerenciá-lo.", ephemeral=True)
                    return

                try:
                    if action_type == "addrole":
                        if role in member.roles:
                            await member.remove_roles(role, reason="MsgAuto: toggle remove role")
                            await inter.response.send_message(f"{emoji.correct} Cargo removido: {role.mention}", ephemeral=True)
                        else:
                            await member.add_roles(role, reason="MsgAuto: toggle add role")
                            await inter.response.send_message(f"{emoji.correct} Cargo adicionado: {role.mention}", ephemeral=True)
                    elif action_type == "removerole":
                        if role in member.roles:
                            await member.remove_roles(role, reason="MsgAuto: remove role")
                            await inter.response.send_message(f"{emoji.correct} Cargo removido: {role.mention}", ephemeral=True)
                        else:
                            await inter.response.send_message(f"{emoji.warn} Você não possui o cargo {role.mention}.", ephemeral=True)
                except disnake.Forbidden:
                    await inter.response.send_message(f"{emoji.wrong} Ocorreu um erro de permissão ao tentar gerenciar o cargo.", ephemeral=True)

    @staticmethod
    async def _send_built_message(target, built_message: dict, ephemeral: bool = False):
        kwargs = {"allowed_mentions": disnake.AllowedMentions.none()}
        if ephemeral:
            kwargs["ephemeral"] = True

        # Verificar se está vazio
        components = built_message.get("components")
        has_components = bool(components and (isinstance(components, list) and len(components) > 0))
        is_empty = not any([
            built_message.get("content"),
            built_message.get("embed"),
            has_components,
            built_message.get("files")
        ])
        if is_empty:
            if isinstance(target, disnake.Interaction):
                await target.followup.send("A mensagem automática está vazia.", ephemeral=True)
            return None

        if built_message["mode"] == "v2":
            kwargs["components"] = components
            kwargs["flags"] = built_message.get("flags")
        else:
            if built_message.get("content"):
                kwargs["content"] = built_message["content"]
            if built_message.get("embed"):
                embed_data = built_message["embed"]
                # Check if it's already an Embed object or a dict
                if isinstance(embed_data, disnake.Embed):
                    kwargs["embed"] = embed_data
                else:
                    normalized_data = utils.normalize_embed_data(embed_data)
                    kwargs["embed"] = disnake.Embed.from_dict(normalized_data)
            if built_message.get("components"):
                kwargs["components"] = built_message["components"]
            if built_message.get("files"):
                kwargs["files"] = built_message["files"]
        
        if isinstance(target, disnake.Interaction):
            return await target.followup.send(**kwargs)
        elif isinstance(target, (disnake.TextChannel, disnake.DMChannel)):
            return await target.send(**kwargs)
        return None

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        cid = inter.component.custom_id
        if not (cid.startswith("MsgAuto_") or cid.startswith("MA_")): return

        if cid == "MsgAuto_SelectCanal":
            canal_id = inter.values[0]
            await inter.response.send_modal(ConfigurarIntervaloModal(canal_id))

        elif cid == "MsgAuto_SelecionarParaEditar":
            await inter.response.defer()
            msg_id = inter.values[0]
            if msg_id == "ignore":
                return
            await inter.edit_original_message(components=self.PainelEditor(self.bot, msg_id))

        elif cid.startswith("MsgAuto_EditarConfig_Canal:"):
            await inter.response.defer()
            msg_id = cid.split(":", 1)[1]
            novo_canal_id = inter.values[0]
            config = helpers.carregar_config()
            if msg_id in config.get("mensagens", {}):
                config["mensagens"][msg_id]["channel_id"] = novo_canal_id
                helpers.salvar_config(config)
            await inter.edit_original_message(components=self.PainelEditarConfig(self.bot, msg_id))

        elif cid.startswith("MsgAuto_Botao_SelecionarBotao:"):
            await inter.response.defer()
            msg_id = cid.split(":")[1]
            button_id = inter.values[0]
            if button_id == "none":
                return
            components = self.ButtonManager.Button.button_config_panel(msg_id, button_id)
            await inter.edit_original_message(components=components)
            
        elif cid.startswith("MsgAuto_SelectRole:"):
            await inter.response.defer()
            _, action_type, msg_id = cid.split(":", 2)
            role_id = inter.values[0]
            
            editor_data = helpers.get_editor_data(msg_id)
            temp_button = editor_data.get("temp_action_button")
            if temp_button:
                action_data = {"type": action_type, "role_id": role_id}
                if action_type == "toggle_role":
                    action_data["remove_on_click_back"] = True 
                
                temp_button["action"] = action_data
                botoes_list = editor_data.get("botoes", [])
                botoes_list.append(temp_button)
                helpers.set_editor_field(msg_id, "botoes", botoes_list)
                helpers.clear_editor_field(msg_id, "temp_action_button")
            
            await inter.edit_original_message(components=self.PainelEditor(self.bot, msg_id))

        elif cid.startswith("MA_Btn_Style:"):
            await inter.response.defer()
            _, msg_id, button_id = cid.split(":")
            cfg = self.ButtonManager._get_cfg(msg_id)
            button = self.ButtonManager._find_button(cfg, button_id)
            if not button: return
            button.setdefault("button", {})["style"] = inter.values[0]
            self.ButtonManager._save_cfg(msg_id, cfg)
            await inter.edit_original_message(components=self.ButtonManager.Button.button_config_panel(msg_id, button_id))
            
        elif cid.startswith(("MA_Btn_ChgAct:", "MA_Btn_AddRole:", "MA_Btn_RemRole:")):
            parts = cid.split(":")
            base_cid, msg_id, button_id = parts
            cfg = self.ButtonManager._get_cfg(msg_id)
            
            if base_cid == "MA_Btn_ChgAct":
                selected = inter.values[0] if inter.values else None
                data = self.ButtonManager._find_button(cfg, button_id).setdefault("button", {})
                action = data.setdefault("action", {})

                if selected == "DarCargo":
                    data.update(type="action", url=None, disabled=False)
                    action.update(type="addrole")
                    self.ButtonManager._save_cfg(msg_id, cfg)
                    await inter.response.edit_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))

                elif selected == "RemoverCargo":
                    data.update(type="action", url=None, disabled=False)
                    action.update(type="removerole")
                    self.ButtonManager._save_cfg(msg_id, cfg)
                    await inter.response.edit_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))

                elif selected == "MensagemEferema":
                    msg = (action or {}).get("message")
                    if not msg:
                        await inter.response.send_modal(self.ButtonManager.EditarMensagemModal(msg_id, button_id))
                        return
                    data.update(type="message", url=None, action={"message": msg}, disabled=False)
                    self.ButtonManager._save_cfg(msg_id, cfg)
                    await inter.response.edit_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))

                elif selected == "URL":
                    if not data.get("url") or not self.ButtonManager._is_valid_url(data.get("url")):
                        await inter.response.send_modal(self.ButtonManager.EditarURLModal(msg_id, button_id))
                        return
                    data.update(type="url", action={}, disabled=False)
                    self.ButtonManager._save_cfg(msg_id, cfg)
                    await inter.response.edit_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))

                elif selected == "Desativado":
                    data.update(type="disabled", url=None, action={}, disabled=True)
                    self.ButtonManager._save_cfg(msg_id, cfg)
                    await inter.response.edit_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))
                return

            await inter.response.defer()
            if base_cid == "MA_Btn_AddRole":
                tipo = "addrole"
            elif base_cid == "MA_Btn_RemRole":
                tipo = "removerole"

            button = self.ButtonManager._find_button(cfg, button_id)
            if not button: return

            data = button.setdefault("button", {})
            action = data.setdefault("action", {})
            action["type"] = tipo
            data["disabled"] = False
            if inter.values:
                action["role"] = int(inter.values[0])
            else:
                action.pop("role", None) # Remove a role se o usuário desmarcar
            
            self.ButtonManager._save_cfg(msg_id, cfg)
            await inter.edit_original_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))


    @commands.Cog.listener("on_modal_submit")
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        cid = inter.custom_id
        if not (cid.startswith("MsgAuto_") or cid.startswith("MA_")): return

        # Tratamento especial para o /ajuda do container, que não pode ser deferido
        if cid.startswith("MsgAuto_DefinirContainerModal:") and inter.text_values.get("container_content", "").strip() == "/ajuda":
            await inter.response.send_message(
                components=AnunciarHelper.helper("example"), ephemeral=True, flags=disnake.MessageFlags(is_components_v2=True)
            )
            return

        # Lógicas para os modais de edição que possuem msg_id
        if ":" not in inter.custom_id: return
        
        parts = inter.custom_id.split(":")
        base_cid = parts[0]
        
        if base_cid == "MsgAuto_ConfigIntervaloModal":
            try:
                canal_id = cid.split(":", 1)[1]
                intervalo = int(inter.text_values.get("intervalo", "60").strip())
                if intervalo < 1: raise ValueError
                
                msg_id = helpers.create_new_message(canal_id, intervalo)
                await inter.response.edit_message(components=self.PainelEditor(self.bot, msg_id))
            except (ValueError, TypeError):
                # Em caso de erro, atualizar a mensagem original também
                await inter.response.defer()
                # Tentar obter o painel anterior ou um painel padrão
                try:
                    # Se conseguir obter algum painel, atualizar
                    await inter.edit_original_message(components=self.PainelEditor(self.bot, None))
                except:
                    pass
                await inter.followup.send("O intervalo deve ser um número válido maior que 0.", ephemeral=True)
            return
        
        if base_cid == "MA_BtnModal_RegBtn":
            _, msg_id, action, button_id = parts
            cfg = self.ButtonManager._get_cfg(msg_id)
            
            emoji_input = inter.text_values.get("emoji", "")
            if emoji_input and not self.ButtonManager.validar_emoji(emoji_input, inter.bot):
                await inter.response.defer()
                # Atualizar a mensagem original mesmo em caso de erro
                try:
                    await inter.edit_original_message(components=self.ButtonManager.Button.button_config_panel(msg_id, button_id))
                except:
                    pass
                await inter.followup.send(f"{emoji.warn} Emoji inválido.", ephemeral=True)
                return

            if action == "create":
                botoes = cfg.setdefault("botoes", [])
                if len(botoes) >= 5:
                    await inter.response.defer()
                    # Atualizar a mensagem original mesmo em caso de erro
                    try:
                        await inter.edit_original_message(components=self.ButtonManager.Button.button_config_panel(msg_id, button_id))
                    except:
                        pass
                    await inter.followup.send("Limite de 5 botões atingido.", ephemeral=True)
                    return
                
                new_button_id = str(uuid.uuid4())
                button_data = {
                    "id": new_button_id, "label": inter.text_values["label"],
                    "button": { "type": "disabled", "emoji": emoji_input or None, "url": None, "style": "gray", "disabled": False, "action": {} }
                }
                botoes.append(button_data)
                self.ButtonManager._save_cfg(msg_id, cfg)
                try:
                    await inter.response.edit_message(components=self.ButtonManager.Button.button_config_panel(msg_id, new_button_id))
                except disnake.NotFound:
                    await inter.response.send_message("A mensagem expirou. Use o comando novamente.", ephemeral=True)

            elif action == "edit":
                button = self.ButtonManager._find_button(cfg, button_id)
                if not button: 
                    await inter.response.send_message("Botão não encontrado.", ephemeral=True)
                    return
                button["label"] = inter.text_values["label"]
                button["button"]["emoji"] = emoji_input or None
                self.ButtonManager._save_cfg(msg_id, cfg)
                try:
                    await inter.response.edit_message(components=self.ButtonManager.Button.button_config_panel(msg_id, button_id))
                except disnake.NotFound:
                    await inter.response.send_message("A mensagem expirou. Use o comando novamente.", ephemeral=True)
            return

        elif base_cid == "MA_BtnModal_EditURL":
            _, msg_id, button_id = parts
            cfg = self.ButtonManager._get_cfg(msg_id)
            button = self.ButtonManager._find_button(cfg, button_id)
            if not button: 
                await inter.response.send_message("Botão não encontrado.", ephemeral=True)
                return
            url = inter.text_values.get("url", "").strip()
            if not self.ButtonManager._is_valid_url(url):
                await inter.response.defer()
                # Atualizar a mensagem original mesmo em caso de erro
                try:
                    await inter.edit_original_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))
                except:
                    pass
                await inter.followup.send(f"{emoji.wrong} URL inválida. Use http(s)://", ephemeral=True)
                return
            data = button.setdefault("button", {})
            data["type"] = "url"
            data["url"] = url
            data["action"] = {}
            data["disabled"] = False
            self.ButtonManager._save_cfg(msg_id, cfg)
            try:
                await inter.response.edit_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))
            except disnake.NotFound:
                await inter.response.send_message("A mensagem expirou. Use o comando novamente.", ephemeral=True)
            return

        elif base_cid == "MA_BtnModal_EditMsg":
            _, msg_id, button_id = parts
            cfg = self.ButtonManager._get_cfg(msg_id)
            button = self.ButtonManager._find_button(cfg, button_id)
            if not button: 
                await inter.response.send_message("Botão não encontrado.", ephemeral=True)
                return
            text = inter.text_values.get("message", "").strip()
            data = button.setdefault("button", {})
            data["type"] = "message"
            data["url"] = None
            data["action"] = {"message": text}
            data["disabled"] = False
            self.ButtonManager._save_cfg(msg_id, cfg)
            try:
                await inter.response.edit_message(components=self.ButtonManager.Button.acoes_panel(msg_id, button_id, inter))
            except disnake.NotFound:
                await inter.response.send_message("A mensagem expirou. Use o comando novamente.", ephemeral=True)
            return

        # Modais de edição principais
        msg_id = parts[1]

        if base_cid == "MsgAuto_DefinirMensagemModal":
            editor_data = helpers.get_editor_data(msg_id)
            editor_data["content"] = inter.text_values["message"]
            editor_data.pop("container", None)
            helpers.set_editor_data(msg_id, editor_data)
        
        elif base_cid == "MsgAuto_DefinirEmbedModal":
            def validar_hex(codigo: str) -> str | None:
                if not codigo: return None
                codigo = codigo.strip().lstrip("#")
                if len(codigo) not in (3, 6): return None
                try: int(codigo, 16)
                except ValueError: return None
                return f"#{codigo.upper()}"
            embed_data = {
                "title": inter.text_values.get("embed_title"), "description": inter.text_values.get("embed_description"),
                "color": validar_hex(inter.text_values.get("embed_color")), "footer": inter.text_values.get("embed_footer"),
            }
            editor_data = helpers.get_editor_data(msg_id)
            editor_data["embed"] = embed_data
            editor_data.pop("container", None)
            helpers.set_editor_data(msg_id, editor_data)
        
        elif base_cid == "MsgAuto_DefinirImagensModal":
            editor_data = helpers.get_editor_data(msg_id)
            editor_data["externalImage"] = inter.text_values.get("externalImage") or None
            if "banner" in inter.text_values:
                if "embed" not in editor_data: editor_data["embed"] = {}
                editor_data["embed"]["banner"] = inter.text_values.get("banner") or None
            if "thumbnail" in inter.text_values:
                if "embed" not in editor_data: editor_data["embed"] = {}
                editor_data["embed"]["thumbnail"] = inter.text_values.get("thumbnail") or None
            helpers.set_editor_data(msg_id, editor_data)

        elif base_cid == "MsgAuto_DefinirContainerModal":
            editor_data = helpers.get_editor_data(msg_id)
            editor_data["container"] = inter.text_values["container_content"]
            editor_data.pop("content", None)
            editor_data.pop("embed", None)
            helpers.set_editor_data(msg_id, editor_data)

        elif base_cid == "MsgAuto_EditarConfigModal":
            try:
                novo_intervalo = int(inter.text_values.get("intervalo"))
                if novo_intervalo < 1: raise ValueError
                config = helpers.carregar_config()
                if msg_id in config.get("mensagens", {}):
                    config["mensagens"][msg_id]["intervalo_minutos"] = novo_intervalo
                    helpers.salvar_config(config)
            except (ValueError, TypeError):
                # Em caso de erro, atualizar a mensagem original também
                await inter.response.defer()
                # Atualizar o painel mesmo em caso de erro
                await inter.edit_original_message(components=self.PainelEditor(self.bot, msg_id))
                await inter.followup.send("Intervalo inválido.", ephemeral=True)
                return 
        
        await inter.response.edit_message(components=self.PainelEditor(self.bot, msg_id))


def setup(bot: commands.Bot):
    bot.add_cog(MsgAutoCog(bot))
