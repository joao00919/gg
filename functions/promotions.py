"""Validação de promoções de produtos sem alterar o contrato do gateway.

O módulo trabalha com Decimal e só converte para ``float`` na fronteira de
compatibilidade com o código legado do carrinho.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Optional

_MONEY = Decimal("0.01")


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_active_promotion(
    product: Mapping[str, Any],
    field: Optional[Mapping[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
) -> Optional[Mapping[str, Any]]:
    """Retorna a promoção válida do campo ou do produto.

    Promoções de campo têm precedência sobre a promoção global. Limite total,
    período e status são sempre validados no backend.
    """
    promotion = None
    if field:
        field_promotion = field.get("promotion")
        if isinstance(field_promotion, Mapping) and field_promotion.get("active"):
            promotion = field_promotion
    if promotion is None:
        candidate = product.get("promotion")
        if isinstance(candidate, Mapping):
            promotion = candidate
    if not promotion or not promotion.get("active", False):
        return None

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    starts_at = _datetime(promotion.get("starts_at"))
    ends_at = _datetime(promotion.get("ends_at"))
    if starts_at and current < starts_at:
        return None
    if ends_at and current > ends_at:
        return None

    limit = promotion.get("limit")
    uses = int(promotion.get("uses", 0) or 0)
    if limit not in (None, ""):
        try:
            if uses >= max(0, int(limit)):
                return None
        except (TypeError, ValueError):
            return None
    return promotion


def get_effective_price(
    product: Mapping[str, Any],
    field: Mapping[str, Any],
    *,
    now: Optional[datetime] = None,
) -> float:
    """Calcula o preço efetivo validado, preservando compatibilidade legada."""
    base = _decimal(field.get("price", 0))
    promotion = get_active_promotion(product, field, now=now)
    if not promotion:
        return float(base)

    candidate = _decimal(promotion.get("price"))
    # Promoção inválida ou maior/igual ao preço normal não altera o valor.
    if candidate <= 0 or candidate >= base:
        return float(base)
    return float(candidate)


def promotion_label(product: Mapping[str, Any], field: Mapping[str, Any]) -> Optional[str]:
    """Texto simples para painéis, sem expor dados administrativos."""
    promotion = get_active_promotion(product, field)
    if not promotion:
        return None
    effective = _decimal(get_effective_price(product, field))
    base = _decimal(field.get("price", 0))
    if effective >= base:
        return None
    return f"R$ {effective:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
