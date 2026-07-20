import disnake
from disnake.ext import commands

from functions.database import database
from functions.emoji import emoji
from functions.utils import utils
from functions.message import message
from functions.perms import perms

class Anunciar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _safe_get(cfg: dict, path: str, default=None):
        cur = cfg
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    @staticmethod
    def is_empty():
        """
        True: if the message is empty
        False: if the message is not empty
        """
        cfg = database.get_document("messages_anunciar") or {}
        msg = cfg.get("message", {}) or {}

        has_container = Anunciar._safe_get(msg, "container") is not None
        has_message   = bool(Anunciar._safe_get(msg, "content"))
        has_embed     = any([
            Anunciar._safe_get(msg, "embed.title"),
            Anunciar._safe_get(msg, "embed.description"),
            Anunciar._safe_get(msg, "embed.color"),
            Anunciar._safe_get(msg, "embed.footer"),
        ])
        has_image     = any([
            Anunciar._safe_get(msg, "externalImage"),
            Anunciar._safe_get(msg, "embed.banner"),
            Anunciar._safe_get(msg, "embed.thumbnail"),
        ])
        buttons_dict  = Anunciar._safe_get(msg, "buttons", []) or []
        has_buttons   = isinstance(buttons_dict, list) and len(buttons_dict) > 0

        has_any       = has_message or has_container or has_embed or has_buttons

        return not has_any

    @staticmethod
    def create_buttons():
        cfg = database.get_document("messages_anunciar") or {}
        msg = cfg.get("message", {}) or {}

        has_container = Anunciar._safe_get(msg, "container") is not None
        has_message   = bool(Anunciar._safe_get(msg, "content"))
        has_embed     = any([
            Anunciar._safe_get(msg, "embed.title"),
            Anunciar._safe_get(msg, "embed.description"),
            Anunciar._safe_get(msg, "embed.color"),
            Anunciar._safe_get(msg, "embed.footer"),
        ])
        has_image     = any([
            Anunciar._safe_get(msg, "externalImage"),
            Anunciar._safe_get(msg, "embed.banner"),
            Anunciar._safe_get(msg, "embed.thumbnail"),
        ])
        buttons_dict  = Anunciar._safe_get(msg, "buttons", []) or []
        has_buttons   = isinstance(buttons_dict, list) and len(buttons_dict) > 0

        others_exist  = has_embed
        has_any       = has_message or has_container or has_embed or has_buttons

        def _row(label: str, define_id: str, delete_id: str, icon_define, has_value: bool, define_disabled: bool = False):  
            return disnake.ui.ActionRow(
                disnake.ui.Button(
                    style=disnake.ButtonStyle.red,
                    custom_id=delete_id,
                    emoji=emoji.delete,
                    disabled=not has_value
                ),
                disnake.ui.Button(
                    label=f"Definir {label}",
                    style=disnake.ButtonStyle.secondary,
                    custom_id=define_id,
                    emoji=icon_define,
                    disabled=define_disabled
                ),            
            )

        components = [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}"),
                disnake.ui.TextDisplay(
                    "Crie, personalize e anuncie mensagens em canais.\n"
                    "Aplique e salve templates de mensagens."
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                _row("Mensagem", "Anunciar_DefinirMensagem", "Anunciar_ApagarMensagem", emoji.message, has_message, define_disabled=False),
                _row("Container", "Anunciar_DefinirContainer", "Anunciar_ApagarContainer", emoji.commands, has_container, define_disabled=others_exist),
                _row("Embed", "Anunciar_DefinirEmbed", "Anunciar_ApagarEmbed", emoji.embed, has_embed, define_disabled=has_container),
                _row("Imagens", "Anunciar_DefinirImagem", "Anunciar_ApagarImagem", emoji.image, has_image, define_disabled=False),
                _row("Botões", "Anunciar_DefinirBotoes", "Anunciar_ApagarBotoes", emoji.plus, has_buttons, define_disabled=False),
            ),

            disnake.ui.ActionRow(
                disnake.ui.Button(label="Apagar Tudo", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id="Anunciar_ApagarTudo", disabled=not has_any),
                disnake.ui.Button(label="Visualizar", style=disnake.ButtonStyle.secondary, emoji=emoji.search, custom_id="Anunciar_Visualizar", disabled=not has_any),
                disnake.ui.Button(label="Postar", style=disnake.ButtonStyle.green, emoji=emoji.arrow, custom_id="Anunciar_PostarMensagem", disabled=not has_any),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Salvar Template", style=disnake.ButtonStyle.secondary, emoji=emoji.save, custom_id="Anunciar_SalvarTemplate", disabled=not has_any),
                disnake.ui.Button(label="Templates Salvos", style=disnake.ButtonStyle.blurple, emoji=emoji.flag, custom_id="Anunciar_Templates"),
            ),
        ]

        return components

    @commands.slash_command(name="anunciar", description="🖊️ | Moderação | Enviar um anúncio para todos os membros.", guild_ids=[utils.obter_server_principal()])
    async def anunciar(self, inter: disnake.ApplicationCommandInteraction):
        await message.wait(inter, send=True)
        
        if not await perms.check(inter):
            await message.error(inter, "Você não tem permissão para usar este comando", send=False)
            return
        
        components = self.create_buttons()
        
        await inter.edit_original_message(
            components=components,
            flags=disnake.MessageFlags(is_components_v2=True),
        )

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Anunciar_PainelInicial":
            await message.wait(inter, send=False)
            components = self.create_buttons()
            await inter.edit_original_message(components=components)

        elif inter.component.custom_id == "Anunciar_ApagarTudo":
            await message.wait(inter, send=False)
            db = database.get_document("messages_anunciar")
            db["message"]["content"] = None
            db["message"]["container"] = None
            db["message"]["externalImage"] = None
            db["message"]["buttons"] = []
            for key in db["message"]["embed"]: db["message"]["embed"][key] = None

            database.save_document("messages_anunciar", {}, db)
            await inter.edit_original_message(components=Anunciar.create_buttons())