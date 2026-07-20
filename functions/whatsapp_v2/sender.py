"""Notificações opcionais por WhatsApp.

Nenhuma credencial é incluída no código. O recurso permanece desativado até que
WHATSAPP_API_URL, WHATSAPP_API_KEY e WHATSAPP_INSTANCE sejam configurados.
"""

import os

import aiohttp

from functions.database import database as db


async def send_whatsapp_v2(number: str, message: str) -> bool:
    api_url = os.getenv("WHATSAPP_API_URL", "").strip().rstrip("/")
    api_key = os.getenv("WHATSAPP_API_KEY", "").strip()
    instance = os.getenv("WHATSAPP_INSTANCE", "").strip()
    if not api_url or not api_key or not instance:
        return False

    clean_number = "".join(filter(str.isdigit, number))
    if len(clean_number) < 10:
        return False

    url = f"{api_url}/message/sendText/{instance}"
    payload = {
        "number": clean_number,
        "text": message,
        "delay": 1200,
        "linkPreview": True,
    }
    headers = {"Content-Type": "application/json", "apikey": api_key}

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                return response.status in {200, 201}
    except (aiohttp.ClientError, TimeoutError):
        return False


async def notify_sale_v2(user_id: str, product_name: str, value: str, buyer_name: str):
    notif_config = db.get_document(f"notif_config_{user_id}") or {}
    if not notif_config.get("enabled"):
        return False

    ddd = str(notif_config.get("ddd", "")).strip()
    number = str(notif_config.get("number", "")).strip()
    if not ddd or not number:
        return False

    message = (
        "Nova venda realizada!\n\n"
        f"Produto: {product_name}\n"
        f"Valor: {value}\n"
        f"Comprador: {buyer_name}\n\n"
        "Enviado automaticamente pelo ZYNEX Systems."
    )
    return await send_whatsapp_v2(f"55{ddd}{number}", message)
