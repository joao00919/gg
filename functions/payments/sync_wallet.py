"""Integração da Carteira Integrada com a API oficial da PurinCash.

A credencial é global para toda a aplicação e é lida apenas do ambiente.
Nenhuma chave é solicitada ou armazenada em painéis do Discord.
"""

from __future__ import annotations

import base64
import json
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import aiohttp

from functions.database import database as db
from modules.loja.personalization.qr_customization import QRCodeGenerator

DEFAULT_API_URL = "https://api.purincash.com/v1"
FINAL_PAYMENT_STATUSES = {"paid", "expired", "refunded", "failed", "cancelled", "canceled"}


def _get_api_url() -> str:
    """Retorna a URL-base da API PurinCash."""
    return (
        os.getenv("PURINCASH_API_URL")
        or os.getenv("ZYNEX_WALLET_API_URL")
        or DEFAULT_API_URL
    ).strip().rstrip("/")


def _get_api_key() -> str:
    """Retorna a chave global da PurinCash, preservando compatibilidade legada."""
    key = (
        os.getenv("PURINCASH_API_KEY")
        or os.getenv("ZYNEX_WALLET_API_KEY")
        or os.getenv("SYNC_WALLET_API_KEY")
        or ""
    ).strip()
    if not key:
        raise ValueError("A Carteira Integrada ainda não foi habilitada pelo operador do sistema.")
    if not key.startswith(("ps_live_", "ps_test_")):
        raise ValueError("A chave PurinCash deve começar com ps_live_ ou ps_test_.")
    return key


def global_wallet_is_configured() -> bool:
    """Indica se a chave global da PurinCash está pronta para uso."""
    try:
        _get_api_key()
        return True
    except ValueError:
        return False


def _load_config() -> dict:
    return db.get_document("payment_configs") or {}


def _wallet_entry() -> dict:
    entry = _load_config().get("sync_wallet") or {}
    if isinstance(entry, dict):
        return entry
    return {"enabled": bool(entry)}


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return default


def _provider_fee_values(entry: Optional[dict] = None) -> tuple[Decimal, Decimal]:
    """Taxa operacional da PurinCash exibida no painel.

    Pode ser ajustada no ambiente para refletir o plano contratado, sem expor
    credenciais ou permitir alteração pelo Discord.
    """
    entry = entry or _wallet_entry()
    percent = _decimal(
        os.getenv("PURINCASH_OPERATION_FEE_PERCENT")
        or entry.get("provider_fee_percent", 0.60)
    )
    fixed = _decimal(
        os.getenv("PURINCASH_OPERATION_FEE_FIXED")
        or entry.get("provider_fee_fixed", 0.25)
    )
    return max(Decimal("0"), percent), max(Decimal("0"), fixed)


def _store_fee_values(entry: Optional[dict] = None) -> tuple[Decimal, Decimal]:
    """Taxa adicional definida pela própria loja."""
    entry = entry or _wallet_entry()
    percent = _decimal(entry.get("store_fee_percent", entry.get("fee_percent", 0)))
    fixed = _decimal(entry.get("store_fee_fixed", entry.get("fee_fixed", 0)))
    percent = max(Decimal("0"), min(percent, Decimal("100")))
    fixed = max(Decimal("0"), fixed)
    return percent, fixed


def calculate_store_fee(value: float, entry: Optional[dict] = None) -> dict[str, float | str]:
    """Calcula valor final, taxa operacional e taxa adicional da loja.

    A taxa da loja é sempre um adicional configurável sobre o produto. A
    responsabilidade define apenas quem cobre a taxa operacional da PurinCash.
    """
    entry = entry or _wallet_entry()
    base = _decimal(value)
    provider_percent, provider_fixed = _provider_fee_values(entry)
    store_percent, store_fixed = _store_fee_values(entry)

    provider_fee = (base * provider_percent / Decimal("100") + provider_fixed).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    store_fee = (base * store_percent / Decimal("100") + store_fixed).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    responsibility = str(entry.get("fee_responsibility") or "").lower().strip()
    if responsibility not in {"store", "client"}:
        responsibility = "store" if bool(entry.get("cover_fee", False)) else "client"

    charged = base + store_fee
    if responsibility == "client":
        charged += provider_fee
        store_net = base + store_fee
    else:
        store_net = max(Decimal("0"), base + store_fee - provider_fee)

    return {
        "base_amount": float(base),
        "fee_amount": float(store_fee),
        "store_fee_amount": float(store_fee),
        "provider_fee_amount": float(provider_fee),
        "charged_amount": float(charged),
        "store_net": float(store_net),
        "responsibility": responsibility,
        "percent": float(store_percent),
        "fixed": float(store_fixed),
        "provider_percent": float(provider_percent),
        "provider_fixed": float(provider_fixed),
    }

def _sanitize_error_message(data: Any, status: int | None = None) -> str:
    if isinstance(data, dict):
        msg = data.get("error") or data.get("message") or data.get("detail")
        if msg:
            return str(msg)[:500]
    text = str(data or "").strip()
    if status == 401:
        return "A chave da PurinCash é inválida, foi revogada ou pertence a outro ambiente."
    if status == 403:
        return text[:500] or "A conta PurinCash não está autorizada para esta operação."
    if status == 429:
        return "O limite temporário de requisições da PurinCash foi atingido. Tente novamente em instantes."
    if status and status >= 500:
        return "A PurinCash está temporariamente indisponível. Tente novamente em instantes."
    return text[:500] or "A PurinCash retornou uma resposta inválida."


async def _request(
    method: str,
    path: str,
    *,
    api_key: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
    timeout: int = 25,
) -> Dict[str, Any]:
    base_url = _get_api_url()
    url = f"{base_url}/{path.lstrip('/')}"
    if query:
        cleaned = {key: value for key, value in query.items() if value is not None}
        if cleaned:
            url = f"{url}?{urlencode(cleaned)}"

    token = api_key or _get_api_key()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ZYNEX-Systems/4.2 PurinCash",
    }
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.request(method.upper(), url, json=payload, headers=headers) as response:
            raw = await response.text()
            try:
                data: Any = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"error": raw}
            if response.status >= 400:
                raise RuntimeError(_sanitize_error_message(data, response.status))
            if not isinstance(data, dict):
                raise RuntimeError("A PurinCash retornou uma resposta inválida.")
            return data


def _callback_url() -> Optional[str]:
    value = (os.getenv("PURINCASH_CALLBACK_URL") or "").strip()
    return value if value.startswith("https://") else None


def _customer_payload(
    name: Optional[str] = None,
    email: Optional[str] = None,
    external_id: Optional[str] = None,
) -> Optional[dict]:
    customer: dict[str, str] = {}
    if name:
        customer["name"] = str(name)[:100]
    if email:
        customer["email"] = str(email)[:255]
    if external_id:
        customer["externalId"] = str(external_id)[:200]
    return customer or None


def _merge_metadata(metadata: Any, fee: dict[str, Any]) -> str:
    data: dict[str, Any] = {}
    if isinstance(metadata, dict):
        data.update(metadata)
    elif isinstance(metadata, str) and metadata.strip():
        try:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                data.update(parsed)
            else:
                data["reference"] = metadata
        except json.JSONDecodeError:
            data["reference"] = metadata
    data.update(
        {
            "provider": "purincash",
            "baseAmountCents": int(round(float(fee["base_amount"]) * 100)),
            "storeFeeCents": int(round(float(fee["store_fee_amount"]) * 100)),
            "providerFeeCents": int(round(float(fee["provider_fee_amount"]) * 100)),
            "chargedAmountCents": int(round(float(fee["charged_amount"]) * 100)),
            "storeNetCents": int(round(float(fee["store_net"]) * 100)),
            "feeResponsibility": fee["responsibility"],
        }
    )
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return encoded[:2048]


async def _add_qr_fields(payment: dict[str, Any]) -> dict[str, Any]:
    pix = payment.get("pix") if isinstance(payment.get("pix"), dict) else {}
    br_code = pix.get("brCode") or payment.get("brCode")
    qr_image = pix.get("qrCodeImage") or payment.get("qrCodeImage")

    payment_id = payment.get("paymentId") or payment.get("id")
    if payment_id:
        payment["payment_id"] = str(payment_id)
    if br_code:
        payment["copy_paste"] = str(br_code)
        payment["pix_copia_cola"] = str(br_code)
        payment["qrCode"] = str(br_code)
    if qr_image:
        payment["qr_code_url"] = qr_image
        if isinstance(qr_image, str) and qr_image.startswith("data:image") and "," in qr_image:
            try:
                encoded = qr_image.split(",", 1)[1]
                payment["qr_code_base64"] = encoded
                payment["qr_code_bytes"] = base64.b64decode(encoded)
            except Exception:
                pass
    if br_code and not payment.get("qr_code_bytes"):
        try:
            payment["qr_code_bytes"] = await QRCodeGenerator.generate_custom_qr(str(br_code))
        except Exception:
            pass
    payment["_provider"] = "sync_wallet"
    payment["provider_name"] = "PurinCash"
    return payment


# ==================== PAGAMENTOS ====================

async def create_sync_payment(
    api_key: str,
    value: float,
    description: Optional[str] = None,
    cover_fee: Optional[bool] = None,
    *,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    customer_external_id: Optional[str] = None,
    metadata: Any = None,
) -> Dict[str, Any]:
    entry = dict(_wallet_entry())
    if cover_fee is not None:
        entry["cover_fee"] = bool(cover_fee)
        entry["fee_responsibility"] = "store" if cover_fee else "client"
    fee = calculate_store_fee(value, entry)
    charged_cents = int(round(float(fee["charged_amount"]) * 100))
    if charged_cents < 80:
        raise ValueError("O valor mínimo aceito pela PurinCash é R$ 0,80.")

    payload: Dict[str, Any] = {
        "valueCents": charged_cents,
        "description": (description or "Pagamento")[:200],
        "paymentMethod": "pix",
        "metadata": _merge_metadata(metadata, fee),
    }
    callback = _callback_url()
    if callback:
        payload["callbackUrl"] = callback
    customer = _customer_payload(customer_name, customer_email, customer_external_id)
    if customer:
        payload["customer"] = customer

    result = await _request("POST", "payments", api_key=api_key, payload=payload)
    result["base_amount"] = fee["base_amount"]
    result["store_fee"] = fee["store_fee_amount"]
    result["provider_fee"] = fee["provider_fee_amount"]
    result["charged_amount"] = fee["charged_amount"]
    result["store_net"] = fee["store_net"]
    result["fee_responsibility"] = fee["responsibility"]
    return await _add_qr_fields(result)


async def check_sync_payment(api_key: str, payment_id: str) -> Dict[str, Any]:
    result = await _request("GET", f"payments/{payment_id}", api_key=api_key)
    status = str(result.get("status") or "pending").lower()
    result["paid"] = status == "paid"
    return await _add_qr_fields(result)


async def list_sync_payments(
    api_key: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    safe_offset = max(0, int(offset))
    return await _request(
        "GET",
        "payments",
        api_key=api_key,
        query={"status": status, "limit": safe_limit, "offset": safe_offset},
    )


async def cancel_sync_payment(api_key: str, payment_id: str) -> Dict[str, Any]:
    """A API pública não possui cancelamento remoto de PIX pendente.

    O carrinho é cancelado localmente e a cobrança expira automaticamente na PurinCash.
    """
    try:
        current = await check_sync_payment(api_key, payment_id)
    except Exception:
        current = {"paymentId": payment_id, "status": "unknown"}
    current["localCancelled"] = True
    current["remoteCancelled"] = False
    return current


async def refund_sync_payment(
    api_key: str,
    payment_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    del api_key, payment_id, reason
    raise RuntimeError("O reembolso deve ser realizado no painel da PurinCash.")


# ==================== SAQUES ====================

async def create_sync_withdraw(
    api_key: str,
    amount: float,
    pix_key: Optional[str] = None,
    pix_key_type: Optional[str] = None,
) -> Dict[str, Any]:
    del pix_key_type  # A PurinCash identifica o tipo da chave automaticamente.
    wallet_address = (pix_key or os.getenv("PURINCASH_PIX_KEY") or "").strip()
    if not wallet_address:
        raise ValueError("Informe a chave PIX do saque para continuar.")
    payload = {
        "method": "pix",
        "amount": float(_decimal(amount)),
        "walletAddress": wallet_address[:100],
    }
    return await _request("POST", "payouts", api_key=api_key, payload=payload)


async def list_sync_withdraws(
    api_key: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sync: bool = False,
) -> Dict[str, Any]:
    del offset, sync
    safe_limit = max(1, min(int(limit), 100))
    return await _request(
        "GET", "payouts", api_key=api_key, query={"status": status, "limit": safe_limit}
    )


async def get_sync_withdraw(api_key: str, withdraw_id: str) -> Dict[str, Any]:
    data = await list_sync_withdraws(api_key, limit=100)
    for item in data.get("payouts", []):
        if str(item.get("id") or item.get("code")) == str(withdraw_id):
            return item
    raise RuntimeError("Saque não encontrado na PurinCash.")


# ==================== CARTEIRA / COMPATIBILIDADE ====================

async def get_sync_balance(api_key: str) -> Dict[str, Any]:
    result = await _request("GET", "wallet", api_key=api_key)
    # Aliases usados pelas telas antigas.
    result.setdefault("availableBalance", result.get("withdrawable", result.get("balance", 0)))
    result.setdefault("available", result.get("withdrawable", result.get("balance", 0)))
    return result


async def get_sync_user(api_key: str) -> Dict[str, Any]:
    return await get_sync_balance(api_key)


async def register_sync_user(*args, **kwargs) -> Dict[str, Any]:
    del args, kwargs
    raise RuntimeError("O cadastro da conta é realizado diretamente no painel da PurinCash.")


async def update_sync_user(*args, **kwargs) -> Dict[str, Any]:
    del args, kwargs
    raise RuntimeError("Atualize os dados da conta diretamente no painel da PurinCash.")


# ==================== WRAPPERS COM SETTINGS ====================

async def create_sync_payment_from_settings(
    value: float,
    description: Optional[str] = None,
    comment: Optional[str] = None,
    cover_fee: Optional[bool] = None,
    *,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    customer_external_id: Optional[str] = None,
    metadata: Any = None,
) -> Dict[str, Any]:
    return await create_sync_payment(
        _get_api_key(),
        value,
        description or comment,
        cover_fee,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_external_id=customer_external_id,
        metadata=metadata,
    )


async def check_sync_payment_from_settings(payment_id: str) -> Dict[str, Any]:
    return await check_sync_payment(_get_api_key(), payment_id)


async def list_sync_payments_from_settings(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    return await list_sync_payments(_get_api_key(), status, limit, offset)


async def cancel_sync_payment_from_settings(payment_id: str) -> Dict[str, Any]:
    return await cancel_sync_payment(_get_api_key(), payment_id)


async def refund_sync_payment_from_settings(
    payment_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    return await refund_sync_payment(_get_api_key(), payment_id, reason)


async def create_sync_withdraw_from_settings(
    amount: float,
    pix_key: Optional[str] = None,
    pix_key_type: Optional[str] = None,
) -> Dict[str, Any]:
    return await create_sync_withdraw(_get_api_key(), amount, pix_key, pix_key_type)


async def get_sync_withdraw_from_settings(withdraw_id: str) -> Dict[str, Any]:
    return await get_sync_withdraw(_get_api_key(), withdraw_id)


async def list_sync_withdraws_from_settings(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sync: bool = False,
) -> Dict[str, Any]:
    return await list_sync_withdraws(_get_api_key(), status, limit, offset, sync)


async def get_sync_user_from_settings() -> Dict[str, Any]:
    return await get_sync_user(_get_api_key())


async def update_sync_user_from_settings(*args, **kwargs) -> Dict[str, Any]:
    return await update_sync_user(*args, **kwargs)


async def get_sync_balance_from_settings() -> Dict[str, Any]:
    return await get_sync_balance(_get_api_key())


__all__ = [
    "calculate_store_fee",
    "create_sync_payment",
    "check_sync_payment",
    "list_sync_payments",
    "cancel_sync_payment",
    "refund_sync_payment",
    "create_sync_withdraw",
    "get_sync_withdraw",
    "list_sync_withdraws",
    "register_sync_user",
    "get_sync_user",
    "update_sync_user",
    "get_sync_balance",
    "create_sync_payment_from_settings",
    "check_sync_payment_from_settings",
    "list_sync_payments_from_settings",
    "cancel_sync_payment_from_settings",
    "refund_sync_payment_from_settings",
    "create_sync_withdraw_from_settings",
    "get_sync_withdraw_from_settings",
    "list_sync_withdraws_from_settings",
    "get_sync_user_from_settings",
    "update_sync_user_from_settings",
    "get_sync_balance_from_settings",
    "global_wallet_is_configured",
]
