from __future__ import annotations

import asyncio
import time

import disnake

from functions.automation_rules import merge_rules
from functions.database import database as db
from functions.emoji import emoji
from modules.loja.referrals.manager import ReferralManager


def _vip_level(points: int) -> str:
    if points >= 5000:
        return "Diamante"
    if points >= 2000:
        return "Ouro"
    if points >= 500:
        return "Prata"
    return "Cliente"


def _update_points_and_vip(
    user_id: int,
    paid_value: float,
    points_per_real: float,
    *,
    add_points: bool = True,
    update_vip: bool = True,
) -> tuple[int, str]:
    doc = db.get_document("loja_customers") or {}
    loyalty = doc.setdefault("loyalty", {}).setdefault(str(user_id), {
        "points": 0,
        "vip_level": "Cliente",
        "history": [],
    })
    points = (
        max(0, int(round(float(paid_value or 0) * float(points_per_real or 1))))
        if add_points else 0
    )
    loyalty["points"] = int(loyalty.get("points", 0)) + points
    if update_vip:
        loyalty["vip_level"] = _vip_level(loyalty["points"])
    loyalty.setdefault("history", []).append({
        "type": "purchase",
        "points": points,
        "paid_value": float(paid_value or 0),
        "timestamp": int(time.time()),
    })
    db.save_document("loja_customers", doc)
    return points, loyalty["vip_level"]


def related_products(product_id: str, limit: int = 3) -> list[dict]:
    products = db.get_document("loja_products") or {}
    product = products.get(product_id) or {}
    ids = product.get("related_products") or []
    result = []
    for related_id in ids:
        if str(related_id) == str(product_id):
            continue
        related = products.get(str(related_id)) or products.get(related_id)
        if related:
            result.append({"id": str(related_id), "name": related.get("name", "Produto")})
        if len(result) >= max(0, min(int(limit), 3)):
            break
    return result


async def _send_first_purchase_message(*, bot, user: disnake.User, config: dict) -> None:
    if not config.get("enabled", True):
        return
    text = str(config.get("message") or "").strip()
    if not text or text.lower() in {"não", "nao", "no", "off"}:
        return
    text = text.replace("{user}", user.mention).replace("{user_name}", str(user))
    destination = str(config.get("destination") or "dm").strip().lower()
    target = None
    try:
        if destination == "dm":
            target = user.dm_channel or await user.create_dm()
        elif destination.isdigit():
            target = bot.get_channel(int(destination))
    except Exception:
        target = None
    if target is None:
        return
    components = None
    label = str(config.get("button_text") or "").strip()
    url = str(config.get("button_url") or "").strip()
    if label and url.startswith(("http://", "https://")):
        components = [disnake.ui.ActionRow(disnake.ui.Button(label=label[:80], url=url, style=disnake.ButtonStyle.url))]
    try:
        await target.send(text[:2000], components=components)
    except Exception:
        pass


async def process_approved_purchase(*, bot, user: disnake.User, purchase_id: str,
                                    product_id: str, paid_value: float,
                                    referral_code: str | None = None,
                                    thread=None) -> dict:
    """Executa somente depois da confirmação do pagamento e é idempotente por pedido."""
    events = db.get_document("post_payment_events") or {"processed": {}}
    if purchase_id in (events.get("processed") or {}):
        return events["processed"][purchase_id]

    prior_user_purchases = [
        item for item in (events.get("processed") or {}).values()
        if str((item or {}).get("user_id")) == str(user.id)
    ]
    is_first_purchase = not prior_user_purchases

    settings = merge_rules(db.get_document("automation_rules") or {}).get("payment", {})
    points = 0
    vip = "Cliente"
    commission = 0.0

    if settings.get("add_points", True) or settings.get("update_vip", True):
        points, vip = _update_points_and_vip(
            user.id,
            paid_value,
            settings.get("points_per_real", 1),
            add_points=bool(settings.get("add_points", True)),
            update_vip=bool(settings.get("update_vip", True)),
        )

    if referral_code:
        commission = ReferralManager.approve(referral_code, user.id, purchase_id, paid_value)

    recommendations = related_products(product_id, 3)
    if recommendations:
        text = "\n".join(f"• **{item['name']}**" for item in recommendations)
        buttons = disnake.ui.ActionRow(
            *(
                disnake.ui.Button(
                    label=str(item["name"])[:80],
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.cart,
                    custom_id=f"buy_product:{item['id']}",
                )
                for item in recommendations
            )
        )
        try:
            await user.send(
                f"{emoji.cardbox} **Clientes que compraram este produto também escolheram:**\n{text}",
                components=[buttons],
            )
        except Exception:
            pass

    personalization = db.get_document("loja_personalization") or {}
    if is_first_purchase:
        await _send_first_purchase_message(
            bot=bot, user=user, config=personalization.get("first_purchase_message") or {}
        )

    result = {
        "processed_at": int(time.time()),
        "user_id": int(user.id),
        "points": points,
        "vip_level": vip,
        "commission": commission,
        "recommendations": [item["id"] for item in recommendations],
        "review_enabled": bool(settings.get("enable_review", True)),
    }
    events.setdefault("processed", {})[purchase_id] = result
    db.save_document("post_payment_events", events)
    return result
