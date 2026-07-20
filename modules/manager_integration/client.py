import asyncio
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

import aiohttp


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _signature(secret: str, timestamp: str, raw_body: str) -> str:
    message = f"{timestamp}.{raw_body}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest().hex()


def _signature_base64url(secret: str, timestamp: str, raw_body: str) -> str:
    import base64
    message = f"{timestamp}.{raw_body}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


async def prozynex_purchase(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    manager_url = _env("MANAGER_API_URL").rstrip("/")
    api_key = _env("MANAGER_INTERNAL_API_KEY")
    signature_secret = _env("MANAGER_SALES_API_KEY") or api_key
    if not manager_url or not api_key or not signature_secret:
        return None

    raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    timestamp = str(int(time.time() * 1000))
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "x-timestamp": timestamp,
        "x-signature": _signature_base64url(signature_secret, timestamp, raw_body),
    }
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{manager_url}/internal/v1/purchases",
            data=raw_body.encode("utf-8"),
            headers=headers,
        ) as response:
            text = await response.text()
            if response.status not in (200, 201):
                raise RuntimeError(f"Manager recusou a compra ({response.status}): {text[:300]}")
            return json.loads(text) if text else {"ok": True}


async def notify_manager_for_cart(cart_id: str, cart: Dict[str, Any], products: Dict[str, Any], user: Any) -> None:
    items = cart.get("items") or []
    for index, item in enumerate(items):
        product_id = item.get("product_id")
        field_id = item.get("campo_id")
        product = products.get(product_id, {}) if isinstance(products, dict) else {}
        field = (product.get("campos") or {}).get(field_id, {}) if isinstance(product, dict) else {}
        integration = {}
        integration.update(product.get("manager_integration") or {})
        integration.update(field.get("manager_integration") or {})
        plan_slug = integration.get("plan_slug")
        if not plan_slug:
            continue

        period_days = int(integration.get("period_days") or 30)
        item_total = float(item.get("item_total") or 0)
        amount_in_cents = max(50, int(round(item_total * 100)))
        discord_id = str(getattr(user, "id", cart.get("user_id", "")))
        username = str(getattr(user, "name", cart.get("username", "cliente")))
        payment_data = cart.get("payment_data") or {}
        external_id = (
            payment_data.get("payment_id")
            or (payment_data.get("provider") or {}).get("payment_id")
            or f"zynex-{cart_id}"
        )
        payload = {
            "idempotencyKey": f"zynex:{cart_id}:{index}:{product_id}:{field_id}",
            "buyerDiscordId": discord_id,
            "buyerUsername": username,
            "applicationName": integration.get("application_name") or product.get("name") or "ZYNEX Systems",
            "discordApplicationId": integration.get("discord_application_id") or None,
            "linkedGuildId": str(cart.get("guild_id")) if cart.get("guild_id") else None,
            "hostingExternalId": integration.get("hosting_external_id") or os.getenv("MANAGER_APPLICATION_ID") or None,
            "planSlug": str(plan_slug),
            "periodDays": period_days,
            "paymentExternalId": str(external_id),
            "amountInCents": amount_in_cents,
            "currency": "BRL",
            "paymentProvider": str(cart.get("payment_method") or "zynex-sales"),
            "autoActivate": True,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        try:
            result = await prozynex_purchase(payload)
            if result:
                print(f"[Manager] Compra {cart_id} prozynexada: {result.get('applicationId')}")
        except Exception as error:
            print(f"[Manager] Falha ao prozynexar compra {cart_id}: {error}")


def schedule_manager_notification(cart_id: str, cart: Dict[str, Any], products: Dict[str, Any], user: Any) -> None:
    asyncio.create_task(notify_manager_for_cart(cart_id, cart, products, user))
