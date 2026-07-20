from modules.loja.cart import buy_modal


def _documents(wallet_enabled: bool):
    return {
        "pagamentos": {"sync_wallet": wallet_enabled},
        "payment_configs": {
            "sync_wallet": {
                "enabled": wallet_enabled,
                "fee_responsibility": "client",
            }
        },
    }


def test_enabled_global_wallet_is_available_in_checkout(monkeypatch):
    docs = _documents(True)
    monkeypatch.setenv("PURINCASH_API_KEY", "ps_test_regression_key")
    monkeypatch.setattr(buy_modal.db, "get_document", lambda name: docs.get(name, {}))
    buy_modal._payment_methods_cache_buy.update(data=None, timestamp=0, fingerprint=None)

    methods = buy_modal.get_available_payment_methods()

    assert "pix" in methods
    assert methods["pix"]["label"] == "PIX"


def test_wallet_without_global_key_is_not_exposed(monkeypatch):
    docs = _documents(True)
    monkeypatch.delenv("PURINCASH_API_KEY", raising=False)
    monkeypatch.delenv("ZYNEX_WALLET_API_KEY", raising=False)
    monkeypatch.delenv("SYNC_WALLET_API_KEY", raising=False)
    monkeypatch.setattr(buy_modal.db, "get_document", lambda name: docs.get(name, {}))
    buy_modal._payment_methods_cache_buy.update(data=None, timestamp=0, fingerprint=None)

    assert "pix" not in buy_modal.get_available_payment_methods()


def test_loading_emoji_is_the_requested_animation():
    assert str(buy_modal.emoji.loading) == "<a:1389945080172904539:1527386782776164392>"
