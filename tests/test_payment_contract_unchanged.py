from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]


def test_purincash_official_contract_is_present():
    text = (ROOT / "functions" / "payments" / "sync_wallet.py").read_text(encoding="utf-8")
    assert 'DEFAULT_API_URL = "https://api.purincash.com/v1"' in text
    assert '"Authorization": f"Bearer {token}"' in text
    assert '"valueCents"' in text
    assert '"paymentMethod": "pix"' in text
    assert '"callbackUrl"' in text
    assert '"payments"' in text
    assert '"wallet"' in text
    assert '"payouts"' in text
    assert "X-API-Key" not in text


def test_store_fee_and_provider_fee_calculation(monkeypatch):
    monkeypatch.setenv("PURINCASH_OPERATION_FEE_PERCENT", "0.60")
    monkeypatch.setenv("PURINCASH_OPERATION_FEE_FIXED", "0.25")
    from functions.payments.sync_wallet import calculate_store_fee

    preview = calculate_store_fee(
        100,
        {
            "store_fee_percent": 5,
            "store_fee_fixed": 1,
            "fee_responsibility": "client",
        },
    )
    assert preview["store_fee_amount"] == 6.0
    assert preview["provider_fee_amount"] == 0.85
    assert preview["charged_amount"] == 106.85
    assert preview["store_net"] == 106.0


def test_payment_payload_uses_cents_customer_metadata_and_callback(monkeypatch):
    monkeypatch.setenv("PURINCASH_API_KEY", "ps_test_unit_test")
    monkeypatch.setenv("PURINCASH_CALLBACK_URL", "https://example.com/webhooks/purincash")
    monkeypatch.setenv("PURINCASH_OPERATION_FEE_PERCENT", "0")
    monkeypatch.setenv("PURINCASH_OPERATION_FEE_FIXED", "0")

    from functions.payments import sync_wallet

    mocked = AsyncMock(
        return_value={
            "paymentId": "PAY_TEST",
            "status": "pending",
            "pix": {"brCode": "000201TEST"},
        }
    )
    with patch.object(sync_wallet, "_request", mocked):
        result = asyncio.run(
            sync_wallet.create_sync_payment_from_settings(
                10,
                description="Pedido teste",
                customer_name="Cliente",
                customer_external_id="123",
                metadata={"cartId": "CART_1"},
            )
        )

    payload = mocked.await_args.kwargs["payload"]
    assert payload["valueCents"] == 1000
    assert payload["paymentMethod"] == "pix"
    assert payload["callbackUrl"] == "https://example.com/webhooks/purincash"
    assert payload["customer"]["externalId"] == "123"
    assert '"cartId":"CART_1"' in payload["metadata"]
    assert result["payment_id"] == "PAY_TEST"
    assert result["copy_paste"] == "000201TEST"


def test_webhook_signature_route_is_implemented():
    text = (ROOT / "modules" / "manager_integration" / "cog.py").read_text(encoding="utf-8")
    assert 'app.router.add_post("/webhooks/purincash"' in text
    assert 'request.headers.get("X-Webhook-Signature")' in text
    assert 'request.headers.get("X-Webhook-Id")' in text
    assert 'hmac.new(secret.encode("utf-8"), raw, hashlib.sha256)' in text
    assert '"payment.paid"' in text
