"""Personalização da loja reproduzindo o fluxo observado no painel de referência."""
from __future__ import annotations

import json
from typing import Any

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.interaction_runtime import respond_error, respond_panel


def _e(name: str, fallback: str = "config"):
    return getattr(emoji, name, getattr(emoji, fallback, None))


def _accent_kwargs() -> dict:
    colors = db.get_document("custom_colors") or {}
    primary = colors.get("primary")
    if primary:
        try:
            return {"accent_colour": disnake.Colour(int(str(primary).replace("#", ""), 16))}
        except (TypeError, ValueError):
            pass
    return {}


def _config() -> dict[str, Any]:
    data = db.get_document("loja_personalization") or {}
    data.setdefault("purchase_event", {})
    data.setdefault("delivery_message", {})
    data.setdefault("feedback_incentive", {})
    data.setdefault("first_purchase_message", {})
    data.setdefault("after_purchase_message", {})
    return data


def _save(data: dict[str, Any]) -> None:
    db.save_document("loja_personalization", data)


def _components_text(payload: dict) -> str:
    """Extrai textos de um painel para visualização/testes sem depender do Discord."""
    chunks: list[str] = []
    for root in payload.get("components", []) or []:
        try:
            node = root.to_component_dict()
        except Exception:
            continue
        stack = [node]
        while stack:
            current = stack.pop()
            content = current.get("content")
            if content:
                chunks.append(str(content))
            stack.extend(current.get("components") or [])
    return "\n".join(chunks)


class PurchaseMessageModal(disnake.ui.Modal):
    def __init__(self):
        current = _config().get("purchase_event") or {}
        super().__init__(
            title="Configurar Mensagem de Compra",
            custom_id="Loja_PurchaseMessage_Modal",
            components=[
                disnake.ui.TextInput(
                    label="Título da mensagem",
                    custom_id="title",
                    value=str(current.get("title") or "Compra iniciada"),
                    required=False,
                    max_length=100,
                ),
                disnake.ui.TextInput(
                    label="Mensagem da compra",
                    custom_id="message",
                    value=str(current.get("message") or "{user} iniciou uma compra de {product_name}."),
                    placeholder="Variáveis: {user}, {product_name}, {value}, {purchase_id}",
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=1800,
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        data = _config()
        event = data.setdefault("purchase_event", {})
        event["title"] = str(inter.text_values.get("title") or "").strip()
        event["message"] = str(inter.text_values.get("message") or "").strip()
        _save(data)
        await respond_panel(inter, PersonalizarLoja.purchase_panel(inter), prefer_edit=True)


class FirstPurchaseModal(disnake.ui.Modal):
    def __init__(self):
        current = _config().get("first_purchase_message") or {}
        super().__init__(
            title="Mensagem de Primeira Compra",
            custom_id="Loja_FirstPurchase_Modal",
            components=[
                disnake.ui.TextInput(
                    label="Mensagem (escreva 'não' pra desativar)",
                    custom_id="message",
                    value=str(current.get("message") or "Parabéns pela sua primeira compra!"),
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=1600,
                ),
                disnake.ui.TextInput(
                    label="Onde enviar: 'dm' ou ID do canal",
                    custom_id="destination",
                    value=str(current.get("destination") or "dm"),
                    required=True,
                    max_length=30,
                ),
                disnake.ui.TextInput(
                    label="Texto do botão (opcional)",
                    custom_id="button_text",
                    value=str(current.get("button_text") or ""),
                    required=False,
                    max_length=80,
                ),
                disnake.ui.TextInput(
                    label="Link do botão (opcional)",
                    custom_id="button_url",
                    value=str(current.get("button_url") or ""),
                    required=False,
                    max_length=400,
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        message_text = str(inter.text_values.get("message") or "").strip()
        data = _config()
        data["first_purchase_message"] = {
            "enabled": message_text.lower() not in {"não", "nao", "no", "off"},
            "message": message_text,
            "destination": str(inter.text_values.get("destination") or "dm").strip(),
            "button_text": str(inter.text_values.get("button_text") or "").strip(),
            "button_url": str(inter.text_values.get("button_url") or "").strip(),
        }
        _save(data)
        await respond_panel(inter, PersonalizarLoja.panel(inter), prefer_edit=True)


class AfterPurchaseModal(disnake.ui.Modal):
    def __init__(self):
        data = _config()
        current = data.get("after_purchase_message") or data.get("feedback_incentive") or {}
        super().__init__(
            title="Mensagem Após Compra",
            custom_id="Loja_AfterPurchase_Modal",
            components=[
                disnake.ui.TextInput(
                    label="Mensagem (escreva 'não' pra desativar)",
                    custom_id="message",
                    value=str(current.get("message") or "Obrigado pela compra! Deixe sua avaliação."),
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=1600,
                ),
                disnake.ui.TextInput(
                    label="Enviar após quantos segundos?",
                    custom_id="delay_seconds",
                    value=str(current.get("delay_seconds") or 10),
                    required=True,
                    max_length=8,
                ),
                disnake.ui.TextInput(
                    label="Texto do botão (opcional)",
                    custom_id="button_text",
                    value=str(current.get("button_text") or ""),
                    required=False,
                    max_length=80,
                ),
                disnake.ui.TextInput(
                    label="Link do botão (opcional)",
                    custom_id="button_url",
                    value=str(current.get("button_url") or ""),
                    required=False,
                    max_length=400,
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        message_text = str(inter.text_values.get("message") or "").strip()
        try:
            delay = max(0, min(604800, int(str(inter.text_values.get("delay_seconds") or "10").strip())))
        except ValueError:
            return await inter.response.send_message(f"{_e('wrong')} Informe um tempo válido em segundos.", ephemeral=True)
        payload = {
            "enabled": message_text.lower() not in {"não", "nao", "no", "off"},
            "message": message_text,
            "delay_seconds": delay,
            "button_text": str(inter.text_values.get("button_text") or "").strip(),
            "button_url": str(inter.text_values.get("button_url") or "").strip(),
        }
        data = _config()
        data["after_purchase_message"] = payload
        # Compatibilidade com o envio de feedback já existente.
        data["feedback_incentive"] = {**(data.get("feedback_incentive") or {}), **payload}
        _save(data)
        await respond_panel(inter, PersonalizarLoja.panel(inter), prefer_edit=True)


class ApprovedJsonModal(disnake.ui.Modal):
    def __init__(self):
        current = _config().get("delivery_message") or {}
        raw = current.get("json")
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False, indent=2)
        super().__init__(
            title="Importar JSON",
            custom_id="Loja_Approved_Json_Modal",
            components=[
                disnake.ui.TextInput(
                    label="JSON da mensagem aprovada",
                    custom_id="json",
                    value=str(raw or ""),
                    placeholder='{"title":"Compra aprovada","description":"Seu produto foi entregue."}',
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=3800,
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        raw = str(inter.text_values.get("json") or "").strip()
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("o JSON precisa ser um objeto")
        except (json.JSONDecodeError, ValueError) as exc:
            return await inter.response.send_message(f"{_e('wrong')} JSON inválido: {str(exc)[:150]}", ephemeral=True)
        data = _config()
        delivery = data.setdefault("delivery_message", {})
        delivery["json"] = parsed
        delivery["title"] = str(parsed.get("title") or delivery.get("title") or "Compra aprovada")
        delivery["message"] = str(parsed.get("description") or parsed.get("message") or delivery.get("message") or "")
        _save(data)
        await respond_panel(inter, PersonalizarLoja.approved_panel(inter), prefer_edit=True)


class ApprovedButtonModal(disnake.ui.Modal):
    def __init__(self, button_key: str, mode: str):
        delivery = _config().get("delivery_message") or {}
        buttons = delivery.get("buttons") or {}
        current = buttons.get(button_key) or {}
        is_emoji = mode == "emoji"
        super().__init__(
            title=f"{'Emoji' if is_emoji else 'Label'} do botão",
            custom_id=f"Loja_Approved_Button_Modal:{button_key}:{mode}",
            components=[
                disnake.ui.TextInput(
                    label="Emoji do botão" if is_emoji else "Texto do botão",
                    custom_id="value",
                    value=str(current.get("emoji" if is_emoji else "label") or ("Comprar" if button_key == "buy" and not is_emoji else "Feedbacks" if not is_emoji else "")),
                    required=False,
                    max_length=100,
                )
            ],
        )
        self.button_key = button_key
        self.mode = mode

    async def callback(self, inter: disnake.ModalInteraction):
        data = _config()
        delivery = data.setdefault("delivery_message", {})
        buttons = delivery.setdefault("buttons", {})
        button = buttons.setdefault(self.button_key, {})
        button["emoji" if self.mode == "emoji" else "label"] = str(inter.text_values.get("value") or "").strip()
        button.setdefault("enabled", True)
        _save(data)
        await respond_panel(inter, PersonalizarLoja.approved_panel(inter), prefer_edit=True)


class PersonalizarLoja(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def panel(inter: disnake.Interaction) -> dict:
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        return PersonalizarLoja._panel_embed(inter) if mode == "embed" else PersonalizarLoja._panel_components(inter)

    @staticmethod
    def _description() -> str:
        return (
            "**Mensagem da Compra**\n"
            "Configure a mensagem que será definida no comando `/set` (Modo Legacy - Personalizado).\n"
            "**Mensagem de Compra Aprovada**\n"
            "Configure a mensagem que será enviada quando uma compra for aprovada.\n"
            "**Mensagem de Primeira Compra**\n"
            "Parabeniza o cliente que compra pela primeira vez.\n"
            "**Mensagem Após Compra**\n"
            "Lembre o cliente de deixar um feedback alguns segundos após a compra."
        )

    @staticmethod
    def _buttons() -> list[disnake.ui.ActionRow]:
        return [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Mensagem de Compra", emoji=_e("reload"), custom_id="Loja_Message:purchase"),
                disnake.ui.Button(label="Mensagem de Compra Aprovada", emoji=_e("edit"), custom_id="Loja_Message:approved"),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Mensagem de Primeira Compra", emoji=_e("fire"), custom_id="Loja_Message:first_purchase"),
                disnake.ui.Button(label="Mensagem Após Compra", emoji=_e("thunder"), custom_id="Loja_Message:after_purchase"),
            ),
        ]

    @staticmethod
    def _panel_components(inter: disnake.Interaction) -> dict:
        return {"components": [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {_e('zenyx2')}\n-# Painel > Loja > **Personalizar**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(PersonalizarLoja._description()),
                disnake.ui.Separator(),
                *PersonalizarLoja._buttons(),
                **_accent_kwargs(),
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=_e("back"), custom_id="Painel_Loja")),
        ]}

    @staticmethod
    def _panel_embed(inter: disnake.Interaction) -> dict:
        embed = disnake.Embed(title="Personalizar Loja", description="-# Painel > Loja > **Personalizar**\n\n" + PersonalizarLoja._description())
        return {"embed": embed, "components": PersonalizarLoja._buttons() + [disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=_e("back"), custom_id="Painel_Loja"))]}

    @staticmethod
    def purchase_panel(inter: disnake.Interaction) -> dict:
        return {"components": [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {_e('zenyx2')}\n-# Painel > Loja > Personalizar > **Mensagem de Compra**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "**Configurar Mensagem de Compra**\nEdite a mensagem que será enviada quando um usuário realizar uma compra.\n"
                    "**Resetar Mensagem de Compra**\nResete a mensagem de compra para o padrão do sistema.\n"
                    "**Atualizar Todas Mensagens de Compra**\nAtualize todas as mensagens de compra já enviadas pelo bot para o novo modelo configurado."
                ),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Configurar Mensagem de Compra", emoji=_e("edit"), custom_id="Loja_PurchaseMessage_Config"),
                    disnake.ui.Button(label="Resetar Mensagem de Compra", emoji=_e("reload"), custom_id="Loja_PurchaseMessage_Reset"),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Atualizar Todas Mensagens de Compra", emoji=_e("reload"), custom_id="Loja_PurchaseMessage_Sync")
                ),
                **_accent_kwargs(),
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=_e("back"), custom_id="Loja_Personalizar")),
        ]}

    @staticmethod
    def approved_panel(inter: disnake.Interaction) -> dict:
        delivery = _config().get("delivery_message") or {}
        style = str(delivery.get("style") or "embed")
        style_label = {"embed": "Embed Normal", "components": "Components V2", "banner": "Banner"}.get(style, "Embed Normal")
        json_ready = isinstance(delivery.get("json"), dict)
        buttons = delivery.get("buttons") or {}
        buy = buttons.get("buy") or {"enabled": True, "label": "Comprar", "emoji": "Emoji Padrão"}
        feedback = buttons.get("feedback") or {"enabled": True, "label": "Feedbacks", "emoji": ""}
        def state(item: dict) -> str:
            return "🟢" if item.get("enabled", True) else "🔴"
        return {"components": [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {_e('zenyx2')}\n-# Painel > Loja > Personalizar > **Mensagem de Compra Aprovada**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"**Modo Atual:** `{style_label}`\n"
                    f"**JSON:** `{'Configurado' if json_ready else 'Não configurado'}`\n"
                    "-# Importe um embed JSON pelo message.style."
                ),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="Loja_Approved_Style",
                        placeholder=style_label,
                        options=[
                            disnake.SelectOption(label="Embed Normal", value="embed", emoji=_e("textc"), default=style == "embed"),
                            disnake.SelectOption(label="Components V2", value="components", emoji=_e("config"), default=style == "components"),
                            disnake.SelectOption(label="Banner", value="banner", emoji=_e("colors"), default=style == "banner"),
                        ],
                    )
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Importar JSON", style=disnake.ButtonStyle.primary, emoji=_e("textc"), custom_id="Loja_Approved_ImportJson"),
                    disnake.ui.Button(label="Visualizar", emoji=_e("search"), custom_id="Loja_Approved_Preview"),
                    disnake.ui.Button(label="Variáveis", emoji=_e("information", "config"), custom_id="Loja_Approved_Variables"),
                ),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "## Botões da Mensagem\nConfigure os botões que aparecem na mensagem de compra aprovada.\n\n"
                    f"{state(buy)} **Comprar** — `{buy.get('label') or 'Comprar'}` `{buy.get('emoji') or 'Emoji Padrão'}`\n"
                    "-# Link para a mensagem do produto (para outros comprarem)\n\n"
                    f"{state(feedback)} **Feedbacks** — `{feedback.get('label') or 'Feedbacks'}` `{feedback.get('emoji') or ''}`\n"
                    "-# Canal de avaliações configurado globalmente"
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label=("Desativar Comprar" if buy.get("enabled", True) else "Ativar Comprar"), style=disnake.ButtonStyle.danger if buy.get("enabled", True) else disnake.ButtonStyle.success, emoji=_e("off" if buy.get("enabled", True) else "on"), custom_id="Loja_Approved_Toggle:buy"),
                    disnake.ui.Button(label="Emoji", emoji=_e("wand"), custom_id="Loja_Approved_Button:buy:emoji"),
                    disnake.ui.Button(label="Label", emoji=_e("edit"), custom_id="Loja_Approved_Button:buy:label"),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label=("Desativar Feedbacks" if feedback.get("enabled", True) else "Ativar Feedbacks"), style=disnake.ButtonStyle.danger if feedback.get("enabled", True) else disnake.ButtonStyle.success, emoji=_e("off" if feedback.get("enabled", True) else "on"), custom_id="Loja_Approved_Toggle:feedback"),
                    disnake.ui.Button(label="Emoji", emoji=_e("wand"), custom_id="Loja_Approved_Button:feedback:emoji"),
                    disnake.ui.Button(label="Label", emoji=_e("edit"), custom_id="Loja_Approved_Button:feedback:label"),
                ),
                **_accent_kwargs(),
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=_e("back"), custom_id="Loja_Personalizar")),
        ]}

    async def _sync_purchase_messages(self, inter: disnake.MessageInteraction) -> tuple[int, int, int]:
        products = db.get_document("loja_products") or {}
        total = updated = removed = 0
        from ..products.product.send import SendProduct
        send_cog = self.bot.get_cog("SendProduct") if hasattr(self.bot, "get_cog") else None
        if send_cog is None:
            send_cog = SendProduct(self.bot)
        for product_id, product in products.items():
            entries = list(product.get("messages") or [])
            kept: list[dict] = []
            for entry in entries:
                total += 1
                try:
                    if not getattr(inter, "guild", None) or int(entry.get("guild_id") or 0) != inter.guild.id:
                        kept.append(entry)
                        continue
                    channel = inter.guild.get_channel(int(entry.get("channel_id") or 0))
                    if channel is None:
                        removed += 1
                        continue
                    msg = await channel.fetch_message(int(entry.get("message_id") or 0))
                    mode = entry.get("mode")
                    formatted = entry.get("formatted_desc", True)
                    if mode == "legacy":
                        await msg.edit(embed=send_cog._build_legacy_embed(product, inter.guild, formatted_desc=formatted), components=send_cog._create_buy_button(product_id))
                    else:
                        await msg.edit(components=send_cog._build_container(product, image_inside=mode == "container_inside", product_id=product_id, formatted_desc=formatted), flags=disnake.MessageFlags(is_components_v2=True))
                    updated += 1
                    kept.append(entry)
                except disnake.NotFound:
                    removed += 1
                except Exception:
                    kept.append(entry)
            product["messages"] = kept
            products[product_id] = product
        _save_products = getattr(db, "save_document")
        _save_products("loja_products", products)
        return total, updated, removed

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid == "Loja_Personalizar":
            return await respond_panel(inter, self.panel(inter), prefer_edit=True)
        if cid == "Loja_Message:purchase":
            return await respond_panel(inter, self.purchase_panel(inter), prefer_edit=True)
        if cid == "Loja_Message:approved":
            return await respond_panel(inter, self.approved_panel(inter), prefer_edit=True)
        if cid == "Loja_Message:first_purchase":
            return await inter.response.send_modal(FirstPurchaseModal())
        if cid == "Loja_Message:after_purchase":
            return await inter.response.send_modal(AfterPurchaseModal())
        if cid == "Loja_PurchaseMessage_Config":
            return await inter.response.send_modal(PurchaseMessageModal())
        if cid == "Loja_PurchaseMessage_Reset":
            data = _config()
            data["purchase_event"] = {"title": "Compra iniciada", "message": "{user} iniciou uma compra de {product_name}."}
            _save(data)
            return await respond_panel(inter, self.purchase_panel(inter), prefer_edit=True)
        if cid == "Loja_PurchaseMessage_Sync":
            await inter.response.defer(ephemeral=True)
            total, updated, removed = await self._sync_purchase_messages(inter)
            return await inter.followup.send(f"{_e('correct')} Sincronização concluída. Total: `{total}` | Atualizadas: `{updated}` | Removidas: `{removed}`.", ephemeral=True)
        if cid == "Loja_Approved_ImportJson":
            return await inter.response.send_modal(ApprovedJsonModal())
        if cid == "Loja_Approved_Preview":
            delivery = _config().get("delivery_message") or {}
            parsed = delivery.get("json") if isinstance(delivery.get("json"), dict) else {}
            embed = disnake.Embed(
                title=str(parsed.get("title") or delivery.get("title") or "Compra aprovada"),
                description=str(parsed.get("description") or delivery.get("message") or "Seu pagamento foi aprovado e o pedido está sendo processado."),
                color=disnake.Colour.green(),
            )
            return await inter.response.send_message(embed=embed, ephemeral=True)
        if cid == "Loja_Approved_Variables":
            return await inter.response.send_message("**Variáveis disponíveis**\n`{user}` `{product_name}` `{purchase_id}` `{paid_value}` `{delivery_status}` `{guild_name}`", ephemeral=True)
        if cid.startswith("Loja_Approved_Toggle:"):
            key = cid.split(":", 1)[1]
            data = _config()
            button = data.setdefault("delivery_message", {}).setdefault("buttons", {}).setdefault(key, {})
            button["enabled"] = not bool(button.get("enabled", True))
            _save(data)
            return await respond_panel(inter, self.approved_panel(inter), prefer_edit=True)
        if cid.startswith("Loja_Approved_Button:"):
            _, key, mode = cid.split(":", 2)
            return await inter.response.send_modal(ApprovedButtonModal(key, mode))

        # Compatibilidade com recursos já publicados em versões anteriores.
        if cid == "Loja_DoubtButton_Config":
            from .doubt_button import DoubtButtonModal
            return await inter.response.send_modal(DoubtButtonModal())
        if cid == "Loja_DoubtButton_Toggle":
            from .doubt_button import DoubtButtonSystem
            data = db.get_document("loja_doubt_button") or {}
            data["enabled"] = not bool(data.get("enabled", False))
            db.save_document("loja_doubt_button", data)
            return await respond_panel(inter, DoubtButtonSystem.panel_doubt_button(inter), prefer_edit=True)
        if cid == "Loja_QRCode_Config":
            from .qr_customization import QRCustomizationModal
            return await inter.response.send_modal(QRCustomizationModal())
        if cid == "Loja_QRCode_Toggle":
            from .qr_customization import QRCodeGenerator
            data = db.get_document("loja_qr_customization") or {}
            data["enabled"] = not bool(data.get("enabled", False))
            db.save_document("loja_qr_customization", data)
            return await respond_panel(inter, QRCodeGenerator.panel(inter), prefer_edit=True)
        if cid == "Loja_Personalizar_DoubtButton":
            from .doubt_button import DoubtButtonSystem
            return await respond_panel(inter, DoubtButtonSystem.panel_doubt_button(inter), prefer_edit=True)
        if cid == "Loja_Personalizar_QRCode":
            from .qr_customization import QRCodeGenerator
            return await respond_panel(inter, QRCodeGenerator.panel(inter), prefer_edit=True)
        if cid == "product_doubt_button":
            from .doubt_button import DoubtButtonSystem
            return await DoubtButtonSystem.handle_doubt_button(inter)

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid != "Loja_Approved_Style":
            return
        value = str(inter.values[0]) if inter.values else "embed"
        if value not in {"embed", "components", "banner"}:
            return await respond_error(inter, "Estilo inválido.")
        data = _config()
        data.setdefault("delivery_message", {})["style"] = value
        _save(data)
        return await respond_panel(inter, self.approved_panel(inter), prefer_edit=True)


def setup(bot: commands.Bot):
    bot.add_cog(PersonalizarLoja(bot))
