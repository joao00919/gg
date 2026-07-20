from __future__ import annotations

import asyncio
import time
from typing import Optional

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from modules.loja.cart.purchase_manager import PurchaseManager


PURPLE = 0x5865F2
GREEN = 0x57F287


def _money(value: float) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")




def _reviews_enabled() -> bool:
    return bool((db.get_document("loja_reviews_config") or {}).get("enabled", True))

def _reviews_document() -> dict:
    raw = db.get_document("loja_reviews") or {}
    if isinstance(raw, list):
        return {"version": 1, "items": list(raw)}
    raw.setdefault("version", 1)
    raw.setdefault("items", [])
    return raw



def get_purchase_review(purchase_id: str) -> Optional[dict]:
    purchase_id = str(purchase_id)
    for item in _reviews_document().get("items", []):
        if str(item.get("purchase_id")) == purchase_id:
            return item
    return None


def _latest_unreviewed_purchase(user_id: int) -> Optional[dict]:
    for purchase in PurchaseManager.get_user_purchases(user_id, limit=25):
        purchase_id = str(purchase.get("purchase_id") or "")
        if purchase_id and not get_purchase_review(purchase_id):
            return purchase
    return None


def save_purchase_review(*, purchase_id: str, user_id: int, rating: int, comment: str) -> dict:
    purchase = PurchaseManager.get_purchase_by_id(str(purchase_id))
    if not purchase:
        raise ValueError("Compra não encontrada.")
    if str(purchase.get("user_id")) != str(user_id):
        raise PermissionError("Somente o comprador pode avaliar este pedido.")
    if not 1 <= int(rating) <= 5:
        raise ValueError("A nota deve estar entre 1 e 5.")
    if get_purchase_review(str(purchase_id)):
        raise ValueError("Esta compra já foi avaliada.")

    record = {
        "purchase_id": str(purchase_id),
        "user_id": str(user_id),
        "rating": int(rating),
        "comment": str(comment or "").strip()[:1000],
        "created_at": int(time.time()),
        "product": dict(purchase.get("product") or {}),
        "field": dict(purchase.get("field") or {}),
        "pricing": dict(purchase.get("pricing") or {}),
        "metadata": dict(purchase.get("metadata") or {}),
    }
    reviews = _reviews_document()
    reviews["items"].append(record)
    db.save_document("loja_reviews", reviews)
    PurchaseManager.update_purchase(
        str(purchase_id),
        {
            "review": {
                "submitted": True,
                "rating": int(rating),
                "created_at": record["created_at"],
            }
        },
    )
    return record


class PurchaseReviewModal(disnake.ui.Modal):
    def __init__(self, purchase_id: str, initial_rating: Optional[int] = None, feedback_message_id: Optional[int] = None):
        self.purchase_id = str(purchase_id)
        self.feedback_message_id = int(feedback_message_id) if feedback_message_id else None
        super().__init__(
            title="Avaliar Produto",
            custom_id=f"purchase_review_modal:{self.purchase_id}:{self.feedback_message_id or 0}",
            components=[
                disnake.ui.Label(
                    text="Nota de 1 a 5",
                    description="1 = ruim e 5 = excelente",
                    component=disnake.ui.TextInput(
                        custom_id="rating",
                        placeholder="5",
                        value=str(initial_rating or ""),
                        min_length=1,
                        max_length=1,
                        required=True,
                        style=disnake.TextInputStyle.short,
                    ),
                ),
                disnake.ui.Label(
                    text="Comentário",
                    description="Conte como foi sua experiência com o produto e a entrega.",
                    component=disnake.ui.TextInput(
                        custom_id="comment",
                        placeholder="Produto entregue corretamente e atendimento rápido.",
                        max_length=1000,
                        required=False,
                        style=disnake.TextInputStyle.paragraph,
                    ),
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        try:
            rating = int(str(inter.text_values.get("rating", "0")).strip())
            comment = inter.text_values.get("comment", "")
            record = save_purchase_review(
                purchase_id=self.purchase_id,
                user_id=inter.author.id,
                rating=rating,
                comment=comment,
            )
        except PermissionError as exc:
            return await inter.response.send_message(f"{emoji.wrong} {exc}", ephemeral=True)
        except (TypeError, ValueError) as exc:
            return await inter.response.send_message(f"{emoji.wrong} {exc}", ephemeral=True)

        await inter.response.send_message(
            f"{emoji.correct} Avaliação registrada. Obrigado por compartilhar sua experiência!",
            ephemeral=True,
        )

        if self.feedback_message_id and getattr(inter, "channel", None):
            try:
                feedback_message = await inter.channel.fetch_message(int(self.feedback_message_id))
                await feedback_message.delete()
            except Exception:
                pass

        canais = db.get_document("canais") or {}
        channel_id = canais.get("canal_de_feedback")
        guild_id = (record.get("metadata") or {}).get("guild_id")
        guild = None
        try:
            if guild_id and getattr(inter, "bot", None):
                guild = inter.bot.get_guild(int(guild_id))
        except Exception:
            guild = None
        if not channel_id or not guild:
            return
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return

        stars = "★" * int(record["rating"]) + "☆" * (5 - int(record["rating"]))
        product_name = (record.get("product") or {}).get("name") or "Produto"
        comment_text = record.get("comment") or "Sem comentário."
        embed = disnake.Embed(
            title="⭐ Nova avaliação de produto",
            description=(
                f"**Cliente:** {inter.author.mention}\n"
                f"**Produto:** `{product_name}`\n"
                f"**Nota:** `{record['rating']}/5` — {stars}\n\n"
                f"**Comentário**\n{comment_text}"
            ),
            color=disnake.Color(PURPLE),
            timestamp=disnake.utils.utcnow(),
        )
        try:
            await channel.send(embed=embed)
        except Exception:
            pass


def _feedback_buttons(purchase_id: str, feedback_message_id: Optional[int] = None) -> list[disnake.ui.ActionRow]:
    message_token = str(int(feedback_message_id)) if feedback_message_id else "0"
    return [
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="1 ⭐",
                style=disnake.ButtonStyle.grey,
                custom_id=f"purchase_review_quick:{purchase_id}:{message_token}:1",
            ),
            disnake.ui.Button(
                label="2 ⭐",
                style=disnake.ButtonStyle.grey,
                custom_id=f"purchase_review_quick:{purchase_id}:{message_token}:2",
            ),
            disnake.ui.Button(
                label="3 ⭐",
                style=disnake.ButtonStyle.grey,
                custom_id=f"purchase_review_quick:{purchase_id}:{message_token}:3",
            ),
            disnake.ui.Button(
                label="4 ⭐",
                style=disnake.ButtonStyle.green,
                custom_id=f"purchase_review_quick:{purchase_id}:{message_token}:4",
            ),
            disnake.ui.Button(
                label="5 ⭐",
                style=disnake.ButtonStyle.green,
                custom_id=f"purchase_review_quick:{purchase_id}:{message_token}:5",
            ),
        )
    ]


def _build_feedback_payload(*, purchase_id: str, feedback_message_id: Optional[int] = None) -> dict:
    embed = disnake.Embed(
        title="⭐ Avalie sua experiência!",
        description=(
            "Obrigado por comprar conosco! Sua opinião é muito importante para continuarmos melhorando.\n\n"
            "Como você avalia a **qualidade do produto** e a sua **experiência de compra**?"
        ),
        color=disnake.Color(PURPLE),
        timestamp=disnake.utils.utcnow(),
    )
    embed.add_field(
        name="Avaliação Rápida",
        value="Escolha uma das opções abaixo. Depois, você poderá escrever um comentário opcional.",
        inline=False,
    )
    embed.set_footer(text="ZYNEX Systems • Sua avaliação ajuda a melhorar a loja")
    return {"embed": embed, "components": _feedback_buttons(purchase_id, feedback_message_id)}


def _render_template(text: str, values: dict[str, object]) -> str:
    result = str(text or "")
    for key, value in values.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def _build_delivery_payload(
    *,
    purchase_id: str,
    product_name: str,
    field_name: str,
    quantity: int,
    paid_value: float,
    delivered: bool,
) -> dict:
    """Monta a mensagem aprovada usando as opções do painel Personalizar Loja."""
    status = "Entregue" if delivered else "Aguardando entrega"
    config = db.get_document("loja_personalization") or {}
    delivery = config.get("delivery_message") or {}
    raw_json = delivery.get("json") if isinstance(delivery.get("json"), dict) else {}
    style = str(delivery.get("style") or "embed").lower()
    values = {
        "product_name": product_name,
        "purchase_id": purchase_id,
        "paid_value": _money(paid_value),
        "delivery_status": status,
        "quantity": max(1, int(quantity or 1)),
        "field_name": field_name or "Padrão",
    }

    default_title = "📦 Entrega do Produto"
    default_description = (
        f"**Produto:** `{product_name}`\n\n"
        f"**Itens do Pedido:**\n```\n{max(1, int(quantity or 1))}x {product_name}\n```\n"
        f"**Itens Entregues:** `{max(1, int(quantity or 1)) if delivered else 0}`"
    )
    title = _render_template(
        str(raw_json.get("title") or delivery.get("title") or default_title), values
    )
    description = _render_template(
        str(raw_json.get("description") or raw_json.get("message") or delivery.get("message") or default_description), values
    )

    color_value = raw_json.get("color") or delivery.get("color") or PURPLE
    try:
        if isinstance(color_value, str):
            color_value = int(color_value.strip().replace("#", ""), 16)
        color = disnake.Color(int(color_value))
    except (TypeError, ValueError):
        color = disnake.Color(PURPLE)

    embed = disnake.Embed(
        title=title[:256],
        description=description[:4096],
        color=color,
        timestamp=disnake.utils.utcnow(),
    )
    if not (raw_json or delivery.get("message")):
        released_text = (
            "O produto foi liberado nas mensagens desta DM. Guarde os dados em local seguro."
            if delivered
            else "O pagamento foi aprovado. A equipe enviará o produto diretamente nesta DM."
        )
        embed.add_field(name="🔓 Produto Liberado:", value=released_text, inline=False)
        embed.add_field(name="Valor", value=f"`{_money(paid_value)}`", inline=True)
        embed.add_field(name="Status", value=f"`{status}`", inline=True)
        if field_name:
            embed.add_field(name="Opção", value=f"`{field_name}`", inline=True)
    image_url = raw_json.get("image") or raw_json.get("image_url") or delivery.get("image")
    if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
        embed.set_image(url=image_url)
    footer = raw_json.get("footer")
    if isinstance(footer, dict):
        footer = footer.get("text")
    embed.set_footer(text=str(footer or "ZYNEX Systems • Compra protegida")[:2048])

    purchase = PurchaseManager.get_purchase_by_id(str(purchase_id)) or {}
    product_id = str((purchase.get("product") or {}).get("id") or "")
    buttons_config = delivery.get("buttons") or {}
    components = []
    buttons = []
    buy = buttons_config.get("buy") or {}
    feedback = buttons_config.get("feedback") or {}
    if buy.get("enabled", True) and product_id:
        buttons.append(disnake.ui.Button(
            label=str(buy.get("label") or "Comprar")[:80],
            emoji=str(buy.get("emoji") or "🛒")[:100] or None,
            custom_id=f"buy_product:{product_id}",
            style=disnake.ButtonStyle.secondary,
        ))
    if feedback.get("enabled", True) and _reviews_enabled():
        buttons.append(disnake.ui.Button(
            label=str(feedback.get("label") or "Feedbacks")[:80],
            emoji=str(feedback.get("emoji") or "⭐")[:100] or None,
            custom_id=f"purchase_feedback_open:{purchase_id}",
            style=disnake.ButtonStyle.secondary,
        ))
    if buttons:
        components = [disnake.ui.ActionRow(*buttons[:5])]

    if style == "components":
        items = [
            disnake.ui.TextDisplay(f"# {title[:250]}"),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay(description[:3900]),
        ]
        if buttons:
            items.append(disnake.ui.Separator())
            items.append(disnake.ui.ActionRow(*buttons[:5]))
        return {
            "components": [disnake.ui.Container(*items, accent_colour=color)],
            "flags": disnake.MessageFlags(is_components_v2=True),
        }
    return {"embed": embed, "components": components or None}


async def _send_after_purchase_message(dm, purchase_id: str, config: dict) -> int | None:
    if not config.get("enabled", True):
        return None
    text = str(config.get("message") or "").strip()
    if not text or text.lower() in {"não", "nao", "no", "off"}:
        return None
    try:
        delay = max(0, min(604800, int(config.get("delay_seconds") or 0)))
    except (TypeError, ValueError):
        delay = 0
    if delay:
        await asyncio.sleep(delay)
    components = None
    label = str(config.get("button_text") or "").strip()
    url = str(config.get("button_url") or "").strip()
    if label and url.startswith(("http://", "https://")):
        components = [disnake.ui.ActionRow(disnake.ui.Button(label=label[:80], url=url, style=disnake.ButtonStyle.url))]
    elif _reviews_enabled():
        components = _feedback_buttons(purchase_id)
    try:
        msg = await dm.send(text[:2000], components=components)
        return getattr(msg, "id", None)
    except Exception:
        return None


def _latest_delivery_cache(user_id: int) -> Optional[dict]:
    cache = db.get_document("loja_delivery_cache") or {}
    items = cache.get("items") if isinstance(cache, dict) else None
    if not isinstance(items, dict):
        return None
    entry = items.get(str(user_id))
    return entry if isinstance(entry, dict) else None


class PurchaseExperienceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_button_click")
    async def purchase_buttons(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(inter.component, "custom_id", "") or "")

        if (
            custom_id.startswith("delivery_feedback_open:")
            or custom_id.startswith("purchase_feedback_open:")
            or custom_id.startswith("purchase_review_quick:")
            or custom_id.startswith("purchase_review:")
        ) and not _reviews_enabled():
            return await inter.response.send_message(
                f"{emoji.off} O sistema de avaliações está desativado nesta loja.",
                ephemeral=True,
            )

        if custom_id.startswith("delivery_feedback_open:"):
            expected_user = custom_id.split(":", 1)[1]
            if str(inter.author.id) != str(expected_user):
                return await inter.response.send_message(
                    f"{emoji.wrong} Apenas o comprador pode avaliar este produto.", ephemeral=True
                )
            purchase = _latest_unreviewed_purchase(inter.author.id)
            if not purchase:
                return await inter.response.send_message(
                    f"{emoji.time} A compra ainda está sendo registrada. Aguarde alguns segundos e tente novamente.",
                    ephemeral=True,
                )
            purchase_id = str(purchase.get("purchase_id"))
            feedback_message = await inter.channel.send(**_build_feedback_payload(purchase_id=purchase_id))
            try:
                await feedback_message.edit(**_build_feedback_payload(purchase_id=purchase_id, feedback_message_id=feedback_message.id))
            except Exception:
                pass
            return await inter.response.send_message(f"{emoji.correct} Painel de avaliação enviado abaixo.", ephemeral=True)

        if custom_id.startswith("purchase_feedback_open:"):
            purchase_id = custom_id.split(":", 1)[1]
            purchase = PurchaseManager.get_purchase_by_id(purchase_id)
            if not purchase or str(purchase.get("user_id")) != str(inter.author.id):
                return await inter.response.send_message(
                    f"{emoji.wrong} Esta compra não pertence a você.", ephemeral=True
                )
            if get_purchase_review(purchase_id):
                return await inter.response.send_message(
                    f"{emoji.correct} Este produto já foi avaliado.", ephemeral=True
                )
            feedback_message = await inter.channel.send(**_build_feedback_payload(purchase_id=purchase_id))
            try:
                await feedback_message.edit(**_build_feedback_payload(purchase_id=purchase_id, feedback_message_id=feedback_message.id))
            except Exception:
                pass
            return await inter.response.send_message(f"{emoji.correct} Painel de avaliação enviado abaixo.", ephemeral=True)

        if custom_id.startswith("delivery_copy:"):
            expected_user = custom_id.split(":", 1)[1]
            if str(inter.author.id) != str(expected_user):
                return await inter.response.send_message(
                    f"{emoji.wrong} Apenas o comprador pode copiar este produto.", ephemeral=True
                )
            cached = _latest_delivery_cache(inter.author.id)
            if not cached:
                return await inter.response.send_message(
                    f"{emoji.wrong} Não encontrei os dados desta entrega para copiar.", ephemeral=True
                )
            product_name = str(cached.get("product_name") or "Produto")
            delivered_text = str(cached.get("content") or "Conteúdo não informado")[:1800]
            return await inter.response.send_message(
                f"Entrega referente ao produto `{product_name}`:\n```\n{delivered_text}\n```"
            )

        if custom_id.startswith("purchase_review_quick:"):
            parts = custom_id.split(":")
            if len(parts) < 4:
                return await inter.response.send_message(f"{emoji.wrong} Avaliação inválida.", ephemeral=True)
            purchase_id = parts[1]
            feedback_message_id = int(parts[2] or 0) or None
            rating_text = parts[3]
            purchase = PurchaseManager.get_purchase_by_id(purchase_id)
            if not purchase:
                return await inter.response.send_message(
                    f"{emoji.wrong} Esta compra não foi encontrada.", ephemeral=True
                )
            if str(purchase.get("user_id")) != str(inter.author.id):
                return await inter.response.send_message(
                    f"{emoji.wrong} Somente o comprador pode avaliar este pedido.", ephemeral=True
                )
            if get_purchase_review(purchase_id):
                return await inter.response.send_message(
                    f"{emoji.correct} Esta compra já foi avaliada.", ephemeral=True
                )
            try:
                rating = int(rating_text)
            except Exception:
                rating = None
            return await inter.response.send_modal(PurchaseReviewModal(purchase_id, initial_rating=rating, feedback_message_id=feedback_message_id))

        if custom_id.startswith("purchase_review:"):
            purchase_id = custom_id.split(":", 1)[1]
            purchase = PurchaseManager.get_purchase_by_id(purchase_id)
            if not purchase or str(purchase.get("user_id")) != str(inter.author.id):
                return await inter.response.send_message(
                    f"{emoji.wrong} Somente o comprador pode avaliar este pedido.", ephemeral=True
                )
            if get_purchase_review(purchase_id):
                return await inter.response.send_message(
                    f"{emoji.correct} Esta compra já foi avaliada.", ephemeral=True
                )
            return await inter.response.send_modal(PurchaseReviewModal(purchase_id))


async def send_purchase_dm(
    *,
    user: disnake.User,
    purchase_id: str,
    product_name: str,
    field_name: str,
    quantity: int,
    paid_value: float,
    delivered: bool,
) -> Optional[disnake.DMChannel]:
    """Confirma a compra na DM sem duplicar a entrega automática."""
    try:
        existing = PurchaseManager.get_purchase_by_id(str(purchase_id)) or {}
        previous = existing.get("delivery_confirmation") or {}
        dm = user.dm_channel or await user.create_dm()

        metadata = existing.get("metadata") or {}
        delivery_type = str(metadata.get("delivery_type") or "").lower()
        automatic_cart_delivery = delivered and delivery_type == "automatic" and metadata.get("cart_id")
        already_sent_receipt = previous.get("dm_sent") and int(previous.get("dm_channel_id") or 0) == int(dm.id)
        feedback_sent = bool(previous.get("feedback_sent"))

        if not automatic_cart_delivery and not already_sent_receipt:
            payload = _build_delivery_payload(
                purchase_id=purchase_id,
                product_name=product_name,
                field_name=field_name,
                quantity=quantity,
                paid_value=paid_value,
                delivered=delivered,
            )
            await dm.send(**payload)

        feedback_message_id = previous.get("feedback_message_id")
        if delivered and _reviews_enabled() and not get_purchase_review(str(purchase_id)) and not feedback_sent:
            personalization = db.get_document("loja_personalization") or {}
            after_config = personalization.get("after_purchase_message") or {}
            if after_config:
                asyncio.create_task(_send_after_purchase_message(dm, str(purchase_id), after_config))
            else:
                feedback_message = await dm.send(**_build_feedback_payload(purchase_id=purchase_id))
                feedback_message_id = feedback_message.id
                try:
                    await feedback_message.edit(**_build_feedback_payload(purchase_id=purchase_id, feedback_message_id=feedback_message.id))
                except Exception:
                    pass

        PurchaseManager.update_purchase(
            purchase_id,
            {
                "delivery_confirmation": {
                    "dm_sent": True,
                    "dm_channel_id": dm.id,
                    "sent_at": int(time.time()),
                    "delivered": bool(delivered),
                    "feedback_sent": bool(delivered),
                    "feedback_message_id": feedback_message_id,
                }
            },
        )
        return dm
    except (disnake.Forbidden, disnake.HTTPException):
        PurchaseManager.update_purchase(
            purchase_id,
            {
                "delivery_confirmation": {
                    "dm_sent": False,
                    "sent_at": int(time.time()),
                    "delivered": bool(delivered),
                }
            },
        )
        return None


async def send_thread_delivery_notice(
    *,
    thread,
    user: disnake.User,
    dm_channel: Optional[disnake.DMChannel],
    purchase_ids: list[str],
    delivered: bool,
) -> None:
    """Envia a confirmação profissional de pagamento no carrinho."""
    if not thread:
        return

    purchases = [PurchaseManager.get_purchase_by_id(item) for item in purchase_ids]
    purchases = [item for item in purchases if item]
    close_at = int(time.time()) + 180

    product_lines = []
    total_value = 0.0
    total_quantity = 0
    for purchase in purchases:
        name = (purchase.get("product") or {}).get("name") or "Produto"
        quantity = max(1, int(purchase.get("quantity") or 1))
        value = float((purchase.get("pricing") or {}).get("final_price") or 0)
        total_value += value
        total_quantity += quantity
        product_lines.append(f"• `{quantity}x` **{name}** — `{_money(value)}`")
    if not product_lines:
        product_lines = ["• Produto processado com sucesso"]

    status = "Entregue" if delivered else "Aguardando entrega"
    embed = disnake.Embed(
        title="✅ Pagamento Aprovado!",
        description="Seu pagamento foi processado com sucesso!",
        color=disnake.Color.green(),
        timestamp=disnake.utils.utcnow(),
    )
    embed.add_field(
        name="📋 Informações da Compra",
        value=(
            "\n".join(product_lines)
            + f"\n\n**Quantidade:** `{total_quantity or 1}`"
            + f"\n**Valor:** `{_money(total_value)}`"
            + f"\n**Status:** `{status}`"
        ),
        inline=False,
    )
    delivery_message = (
        "Pagamento aprovado: seu produto foi entregue na DM. Abra suas mensagens diretas para acessar os dados."
        if delivered
        else "A equipe concluirá a entrega diretamente nas suas mensagens privadas (DM)."
    )
    embed.add_field(name="📦 Entrega realizada!" if delivered else "📦 Entrega em andamento", value=delivery_message, inline=False)
    embed.add_field(
        name="🔒 Compra segura",
        value=(
            "Não compartilhe os dados recebidos na DM. Caso precise de ajuda, entre em contato com o suporte.\n"
            f"Este carrinho será fechado em <t:{close_at}:R>."
        ),
        inline=False,
    )
    embed.set_footer(text="ZYNEX Systems • Pagamento confirmado")

    buttons = []
    if dm_channel:
        buttons.append(
            disnake.ui.Button(
                label="Ir para DM",
                style=disnake.ButtonStyle.url,
                emoji="💬",
                url=f"https://discord.com/channels/@me/{dm_channel.id}",
            )
        )
    components = [disnake.ui.ActionRow(*buttons)] if buttons else None
    try:
        await thread.send(embed=embed, components=components)
    except Exception:
        pass


def setup(bot: commands.Bot):
    bot.add_cog(PurchaseExperienceCog(bot))
