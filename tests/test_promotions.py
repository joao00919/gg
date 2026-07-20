from datetime import datetime, timezone

from functions.promotions import get_active_promotion, get_effective_price


def test_active_promotion_uses_decimal_price_and_period():
    product = {"promotion": {"active": False}}
    field = {
        "price": 19.90,
        "promotion": {
            "active": True,
            "price": 14.90,
            "starts_at": "2026-01-01T00:00:00+00:00",
            "ends_at": "2026-12-31T23:59:59+00:00",
            "limit": 10,
            "uses": 1,
        },
    }
    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    assert get_active_promotion(product, field, now=now) is not None
    assert get_effective_price(product, field, now=now) == 14.9


def test_expired_or_invalid_promotion_keeps_normal_price():
    product = {"promotion": {"active": True, "price": 25, "ends_at": "2025-01-01T00:00:00+00:00"}}
    field = {"price": 20}
    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    assert get_active_promotion(product, field, now=now) is None
    assert get_effective_price(product, field, now=now) == 20.0
