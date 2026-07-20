from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.tickets.purchase_link import (
    active_ticket_for_purchase,
    context_from_purchase,
    get_user_purchases,
    mode_requires_purchase,
    selector_payload,
)


class TicketPurchaseLinkTests(unittest.TestCase):
    def setUp(self):
        self.purchase = {
            "purchase_id": "ABC123",
            "timestamp": int(time.time()),
            "product": {"id": "P1", "name": "Netflix"},
            "field": {"id": "F1", "name": "30 dias"},
            "quantity": 1,
            "pricing": {"final_price": 19.9},
            "payment": {"method": "purincash"},
            "delivery": {"items": ["conta@teste.com"], "items_count": 1},
            "metadata": {"delivery_type": "automatic"},
        }

    def test_panel_modes_control_purchase_link(self):
        self.assertFalse(mode_requires_purchase({"ticket_mode": "common"}))
        self.assertTrue(mode_requires_purchase({"ticket_mode": "purchase"}))
        self.assertTrue(mode_requires_purchase({"ticket_mode": "mixed"}))
        self.assertTrue(mode_requires_purchase({"ticket_mode": "warranty"}))
        self.assertFalse(mode_requires_purchase({"ticket_mode": "financial"}))

    def test_selector_lists_real_purchase_and_without_purchase_for_mixed_mode(self):
        panel = {"ticket_mode": "mixed", "purchase_settings": {}}
        with patch(
            "modules.tickets.purchase_link.PurchaseManager.get_user_purchases",
            return_value=[self.purchase],
        ):
            payload = selector_payload(10, "PANEL", panel)

        select = payload["components"][0].children[0]
        values = [option.value for option in select.options]
        self.assertIn("__without_purchase__", values)
        self.assertIn("ABC123", values)
        self.assertIn("Compras encontradas", payload["embed"].title)

    def test_warranty_mode_filters_old_purchase(self):
        old = {**self.purchase, "timestamp": int(time.time()) - 40 * 86400}
        panel = {"ticket_mode": "warranty", "purchase_settings": {"warranty_days": 30}}
        with patch(
            "modules.tickets.purchase_link.PurchaseManager.get_user_purchases",
            return_value=[self.purchase, old],
        ):
            purchases = get_user_purchases(10, panel)
        self.assertEqual([item["purchase_id"] for item in purchases], ["ABC123"])

    def test_context_keeps_purchase_snapshot(self):
        context = context_from_purchase({"ticket_mode": "purchase"}, self.purchase)
        self.assertEqual(context["purchase_id"], "ABC123")
        self.assertEqual(context["purchase"]["product"]["name"], "Netflix")
        self.assertEqual(context["priority"], "high")

    def test_duplicate_purchase_ticket_returns_existing_channel(self):
        channel = SimpleNamespace(id=777, jump_url="https://discord.com/channels/1/777")
        guild = SimpleNamespace(
            get_channel=lambda channel_id: channel if channel_id == 777 else None,
            get_thread=lambda _channel_id: None,
        )
        ticket_data = {
            "panels": {
                "PANEL": {
                    "10": [
                        {
                            "status": "open",
                            "purchase_id": "ABC123",
                            "ticket_id": 777,
                        }
                    ]
                }
            }
        }
        with patch(
            "modules.tickets.purchase_link.db.get_document",
            return_value=ticket_data,
        ):
            existing = active_ticket_for_purchase(guild, 10, "ABC123")
        self.assertIs(existing, channel)


if __name__ == "__main__":
    unittest.main()
