from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import modules.loja.cart.checkout as checkout

ROOT = Path(__file__).resolve().parents[1]


class _HostChannel:
    async def create_thread(self, **kwargs):  # pragma: no cover - shape only
        return kwargs


class _FakeThread:
    def __init__(self, parent=None, parent_id=None):
        self.parent = parent
        self.parent_id = parent_id


def test_cart_thread_created_on_parent_when_interaction_is_inside_thread(monkeypatch):
    parent = _HostChannel()
    thread = _FakeThread(parent=parent)
    inter = SimpleNamespace(channel=thread, guild=SimpleNamespace(get_channel=lambda _id: None))

    monkeypatch.setattr(checkout.disnake, "Thread", _FakeThread)

    assert checkout._resolve_cart_thread_host(inter) is parent


def test_cart_thread_parent_can_be_resolved_by_parent_id(monkeypatch):
    parent = _HostChannel()
    thread = _FakeThread(parent=None, parent_id=123)
    inter = SimpleNamespace(channel=thread, guild=SimpleNamespace(get_channel=lambda channel_id: parent if channel_id == 123 else None))

    monkeypatch.setattr(checkout.disnake, "Thread", _FakeThread)

    assert checkout._resolve_cart_thread_host(inter) is parent


def test_checkout_no_longer_calls_create_thread_directly_on_interaction_channel():
    source = (ROOT / "modules" / "loja" / "cart" / "checkout.py").read_text(encoding="utf-8")
    assert "await inter.channel.create_thread(" not in source
    assert "thread_host = _resolve_cart_thread_host(inter)" in source
