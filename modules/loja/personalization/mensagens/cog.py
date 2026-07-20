"""
Sistema de personalização de mensagens da loja
"""
import disnake
from disnake.ext import commands
from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message


DELIVERY_STYLE_OPTIONS = "embed / components / banner"
FEEDBACK_STYLE_OPTIONS = "embed / components / banner"


class PersonalizarMensagens(commands.Cog):
    """Personalização de mensagens da loja"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _get_config() -> dict:
        config = db.get_document("loja_personalization") or {}
        config.setdefault("purchase_event", {})
        config.setdefault("delivery_message", {})
        config.setdefault("feedback_incentive", {})
        return config

    @staticmethod
    def panel(inter: disnake.MessageInteraction) -> dict:
        """Retorna o painel de personalização de mensagens"""
        mode = db.get_document("custom_mode").get("mode", "components")
        if mode == "embed":
            return PersonalizarMensagens._panel_embed(inter)
        return PersonalizarMensagens._panel_components(inter)

    @staticmethod
    def _panel_components(inter: disnake.MessageInteraction) -> dict:
        """Painel em modo components v2"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        if primary_color_hex:
            container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

        config = PersonalizarMensagens._get_config()
        event_config = config.get("purchase_event", {})
        delivery_config = config.get("delivery_message", {})
        feedback_config = config.get("feedback_incentive", {})

        event_configured = bool(event_config.get("color") or event_config.get("image"))
        delivery_style = delivery_config.get("style", "embed")
        delivery_configured = bool(delivery_config.get("message") or delivery_config.get("title") or delivery_config.get("style"))
        feedback_style = feedback_config.get("style", "components")
        feedback_configured = bool(feedback_config.get("message") is not None)

        return {"components": [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Loja > Personalizar > **Mensagens**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "Configure as mensagens automáticas da sua loja.\n"
                    "Agora você pode deixar a **entrega** e a **avaliação** mais bonitas, completas e com estilo personalizável."
                ),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay("**Configurações Disponíveis**"),
                disnake.ui.TextDisplay(
                    f"{emoji.on if event_configured else emoji.off} **Evento de Compra**\n"
                    f"-# Aparência da mensagem pública de compra\n\n"
                    f"{emoji.on if delivery_configured else emoji.off} **Mensagem de Entrega**\n"
                    f"-# Estilo atual: **{delivery_style}**\n"
                    f"-# Recibo/entrega enviado na DM após pagamento aprovado\n\n"
                    f"{emoji.on if feedback_configured else emoji.off} **Mensagem de Avaliação**\n"
                    f"-# Estilo atual: **{feedback_style}**\n"
                    f"-# Convite para avaliação com visual personalizado"
                ),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Evento de Compra",
                        style=disnake.ButtonStyle.blurple,
                        emoji=emoji.sparkles,
                        custom_id="Loja_Personalizar_EventoCompra"
                    ),
                    disnake.ui.Button(
                        label="Mensagem de Entrega",
                        style=disnake.ButtonStyle.green,
                        emoji=emoji.truck,
                        custom_id="Loja_Personalizar_Entrega"
                    ),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Mensagem de Avaliação",
                        style=disnake.ButtonStyle.blurple,
                        emoji=emoji.star,
                        custom_id="Loja_Personalizar_Feedback"
                    ),
                ),
                **container_kwargs
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Loja_Personalizar"
                )
            )
        ]}

    @staticmethod
    def _panel_embed(inter: disnake.MessageInteraction) -> dict:
        """Painel em modo embed"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        embed_kwargs = {}
        if primary_color_hex:
            embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

        config = PersonalizarMensagens._get_config()
        event_config = config.get("purchase_event", {})
        delivery_config = config.get("delivery_message", {})
        feedback_config = config.get("feedback_incentive", {})

        event_configured = bool(event_config.get("color") or event_config.get("image"))
        delivery_style = delivery_config.get("style", "embed")
        delivery_configured = bool(delivery_config.get("message") or delivery_config.get("title") or delivery_config.get("style"))
        feedback_style = feedback_config.get("style", "components")
        feedback_configured = feedback_config.get("message") is not None

        embed = disnake.Embed(
            title="Personalizar Mensagens",
            description=(
                "-# Painel > Loja > Personalizar > **Mensagens**\n\n"
                "Configure as mensagens automáticas da sua loja.\n"
                "Agora você pode deixar a **entrega** e a **avaliação** mais bonitas, completas e com estilo personalizável.\n\n"
                f"{emoji.on if event_configured else emoji.off} **Evento de Compra**\n"
                f"Mensagem pública quando alguém compra\n\n"
                f"{emoji.on if delivery_configured else emoji.off} **Mensagem de Entrega**\n"
                f"Estilo atual: **{delivery_style}**\n"
                f"Recibo/entrega enviado na DM após pagamento aprovado\n\n"
                f"{emoji.on if feedback_configured else emoji.off} **Mensagem de Avaliação**\n"
                f"Estilo atual: **{feedback_style}**\n"
                f"Convite para avaliação com visual personalizado"
            ),
            **embed_kwargs
        )

        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Evento de Compra",
                    style=disnake.ButtonStyle.blurple,
                    emoji=emoji.sparkles,
                    custom_id="Loja_Personalizar_EventoCompra"
                ),
                disnake.ui.Button(
                    label="Mensagem de Entrega",
                    style=disnake.ButtonStyle.green,
                    emoji=emoji.truck,
                    custom_id="Loja_Personalizar_Entrega"
                ),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Mensagem de Avaliação",
                    style=disnake.ButtonStyle.blurple,
                    emoji=emoji.star,
                    custom_id="Loja_Personalizar_Feedback"
                ),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Loja_Personalizar"
                )
            )
        ]

        return {"embed": embed, "components": components}

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Loja_Personalizar_Mensagens":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter, send=False)
            else:
                await message.wait(inter, send=False)
            panel_data = self.panel(inter)
            await inter.edit_original_message(**panel_data)

        elif inter.component.custom_id == "Loja_Personalizar_EventoCompra":
            await inter.response.send_modal(ConfigurarEventoCompraModal())

        elif inter.component.custom_id == "Loja_Personalizar_Entrega":
            await inter.response.send_modal(ConfigurarEntregaModal())

        elif inter.component.custom_id == "Loja_Personalizar_Feedback":
            await inter.response.send_modal(ConfigurarFeedbackModal())


class ConfigurarEventoCompraModal(disnake.ui.Modal):
    """Modal para configurar visual do evento de compra"""

    def __init__(self):
        config = db.get_document("loja_personalization") or {}
        event_config = config.get("purchase_event", {})
        current_color = event_config.get("color", "")
        current_image = event_config.get("image", "")

        components = [
            disnake.ui.TextInput(
                label="Cor do Evento (Hex)",
                placeholder="Ex: #00FF00 (deixe vazio para cor padrão verde)",
                custom_id="color",
                style=disnake.TextInputStyle.short,
                value=current_color,
                required=False,
                max_length=7
            ),
            disnake.ui.TextInput(
                label="URL da Imagem (Embed)",
                placeholder="https://... (deixe vazio para sem imagem)",
                custom_id="image",
                style=disnake.TextInputStyle.short,
                value=current_image,
                required=False
            )
        ]

        super().__init__(
            title="Configurar Visual do Evento",
            custom_id="ConfigurarEventoCompra_Modal",
            components=components
        )

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter)
        else:
            await message.wait(inter)

        config = db.get_document("loja_personalization") or {}
        config["purchase_event"] = {
            "color": inter.text_values.get("color", "").strip(),
            "image": inter.text_values.get("image", "").strip()
        }
        db.save_document("loja_personalization", config)

        panel_data = PersonalizarMensagens.panel(inter)
        await inter.edit_original_message(**panel_data)


class ConfigurarEntregaModal(disnake.ui.Modal):
    """Modal para configurar a mensagem de entrega/recibo da DM"""

    def __init__(self):
        config = db.get_document("loja_personalization") or {}
        delivery_config = config.get("delivery_message", {})

        components = [
            disnake.ui.TextInput(
                label="Estilo da Entrega",
                placeholder=f"Use: {DELIVERY_STYLE_OPTIONS}",
                custom_id="style",
                style=disnake.TextInputStyle.short,
                value=delivery_config.get("style", "embed"),
                required=False,
                max_length=20
            ),
            disnake.ui.TextInput(
                label="Título da Mensagem",
                placeholder="Ex: Compra aprovada",
                custom_id="title",
                style=disnake.TextInputStyle.short,
                value=delivery_config.get("title", "Compra aprovada"),
                required=False,
                max_length=80
            ),
            disnake.ui.TextInput(
                label="Mensagem da Entrega",
                placeholder="Use variáveis como {product_name}, {purchase_id}, {paid_value}, {delivery_status}",
                custom_id="message",
                style=disnake.TextInputStyle.paragraph,
                value=delivery_config.get("message", ""),
                required=False,
                max_length=1000
            ),
            disnake.ui.TextInput(
                label="Cor da Mensagem (Hex)",
                placeholder="Ex: #22C55E",
                custom_id="color",
                style=disnake.TextInputStyle.short,
                value=delivery_config.get("color", "#22C55E"),
                required=False,
                max_length=7
            ),
            disnake.ui.TextInput(
                label="Imagem/Banner (opcional)",
                placeholder="https://... para usar no estilo banner",
                custom_id="image",
                style=disnake.TextInputStyle.short,
                value=delivery_config.get("image", ""),
                required=False,
                max_length=300
            )
        ]

        super().__init__(
            title="Configurar Mensagem de Entrega",
            custom_id="ConfigurarEntrega_Modal",
            components=components
        )

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter)
        else:
            await message.wait(inter)

        config = db.get_document("loja_personalization") or {}
        config["delivery_message"] = {
            "style": (inter.text_values.get("style", "embed") or "embed").strip().lower(),
            "title": inter.text_values.get("title", "").strip(),
            "message": inter.text_values.get("message", "").strip(),
            "color": inter.text_values.get("color", "").strip(),
            "image": inter.text_values.get("image", "").strip(),
        }
        db.save_document("loja_personalization", config)

        panel_data = PersonalizarMensagens.panel(inter)
        await inter.edit_original_message(**panel_data)


class ConfigurarFeedbackModal(disnake.ui.Modal):
    """Modal para configurar mensagem de incentivo de feedback"""

    def __init__(self):
        config = db.get_document("loja_personalization") or {}
        feedback_config = config.get("feedback_incentive", {})
        current_message = feedback_config.get(
            "message",
            "**Obrigado pela sua compra!** 🎉\n\n"
            "Que tal deixar uma avaliação sobre sua experiência?\n"
            "-# Seu feedback é muito importante para nós!"
        )
        current_button_text = feedback_config.get("button_text", "Avaliar compra")

        components = [
            disnake.ui.TextInput(
                label="Estilo da Avaliação",
                placeholder=f"Use: {FEEDBACK_STYLE_OPTIONS}",
                custom_id="style",
                style=disnake.TextInputStyle.short,
                value=feedback_config.get("style", "components"),
                required=False,
                max_length=20
            ),
            disnake.ui.TextInput(
                label="Título da Avaliação",
                placeholder="Ex: Como foi sua experiência?",
                custom_id="title",
                style=disnake.TextInputStyle.short,
                value=feedback_config.get("title", "Como foi sua experiência?"),
                required=False,
                max_length=80
            ),
            disnake.ui.TextInput(
                label="Mensagem de Incentivo",
                placeholder="Mensagem para incentivar feedback",
                custom_id="message",
                style=disnake.TextInputStyle.paragraph,
                value=current_message,
                required=True,
                max_length=1000
            ),
            disnake.ui.TextInput(
                label="Texto do Botão",
                placeholder="Ex: Avaliar compra",
                custom_id="button_text",
                style=disnake.TextInputStyle.short,
                value=current_button_text,
                required=True,
                max_length=40
            ),
            disnake.ui.TextInput(
                label="Cor da Avaliação (Hex)",
                placeholder="Ex: #5865F2",
                custom_id="color",
                style=disnake.TextInputStyle.short,
                value=feedback_config.get("color", "#5865F2"),
                required=False,
                max_length=7
            )
        ]

        super().__init__(
            title="Configurar Mensagem de Avaliação",
            custom_id="ConfigurarFeedback_Modal",
            components=components
        )

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter)
        else:
            await message.wait(inter)

        config = db.get_document("loja_personalization") or {}
        config["feedback_incentive"] = {
            "style": (inter.text_values.get("style", "components") or "components").strip().lower(),
            "title": inter.text_values.get("title", "").strip(),
            "message": inter.text_values.get("message"),
            "button_text": inter.text_values.get("button_text"),
            "color": inter.text_values.get("color", "").strip(),
        }
        db.save_document("loja_personalization", config)

        panel_data = PersonalizarMensagens.panel(inter)
        await inter.edit_original_message(**panel_data)


def setup(bot: commands.Bot):
    bot.add_cog(PersonalizarMensagens(bot))
