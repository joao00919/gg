from __future__ import annotations

import unittest

from functions.automation_rules import escalate_priority, is_ticket_stale, merge_rules, stock_is_low


class AutomationRuleTests(unittest.TestCase):
    def test_priority_escalation(self):
        self.assertEqual(escalate_priority("normal"), "high")
        self.assertEqual(escalate_priority("high"), "urgent")
        self.assertEqual(escalate_priority("urgent"), "urgent")

    def test_low_stock_threshold(self):
        self.assertTrue(stock_is_low(4, 5))
        self.assertFalse(stock_is_low(5, 5))
        self.assertFalse(stock_is_low("invalido", 5))

    def test_stale_ticket(self):
        ticket = {"status": "open", "created_at": 100}
        self.assertTrue(is_ticket_stale(ticket, now=1901, stale_minutes=30))
        self.assertFalse(is_ticket_stale(ticket, now=1899, stale_minutes=30))
        ticket["status"] = "closed"
        self.assertFalse(is_ticket_stale(ticket, now=9999, stale_minutes=30))

    def test_merge_preserves_defaults(self):
        rules = merge_rules({"stock": {"threshold": 3}})
        self.assertEqual(rules["stock"]["threshold"], 3)
        self.assertTrue(rules["stock"]["notify_admin"])
        self.assertEqual(rules["tickets"]["stale_minutes"], 30)


if __name__ == "__main__":
    unittest.main()
