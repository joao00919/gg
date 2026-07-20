from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from modules.loja.referrals.manager import ReferralManager
from modules.loja.saldo.balance_manager import BalanceManager


class ReferralTests(unittest.TestCase):
    def setUp(self):
        self.store = {
            "referral_config": {
                "enabled": True,
                "prefix": "ZYNEX",
                "commission_percent": 5,
                "referred_discount_percent": 10,
                "max_uses_per_code": 2,
                "minimum_purchase": 1,
            },
            "referrals": {"codes": {}, "owners": {}, "history": []},
            "loja_saldo_users": {"users": {}},
        }

        def get_document(name):
            return deepcopy(self.store.get(name, {}))

        def save_document(name, data):
            self.store[name] = deepcopy(data)

        self.get_patch = patch("modules.loja.referrals.manager.db.get_document", side_effect=get_document)
        self.save_patch = patch("modules.loja.referrals.manager.db.save_document", side_effect=save_document)
        self.balance_get_patch = patch("modules.loja.saldo.balance_manager.db.get_document", side_effect=get_document)
        self.balance_save_patch = patch("modules.loja.saldo.balance_manager.db.save_document", side_effect=save_document)
        self.get_patch.start()
        self.save_patch.start()
        self.balance_get_patch.start()
        self.balance_save_patch.start()

    def tearDown(self):
        patch.stopall()

    def test_anti_self_referral_and_payment_approval(self):
        code = ReferralManager.code_for(100, "João")
        ok, _message, _discount, _entry = ReferralManager.validate(code, 100, 50)
        self.assertFalse(ok)

        ok, _message, discount, _entry = ReferralManager.validate(code, 200, 50)
        self.assertTrue(ok)
        self.assertEqual(discount, 5.0)

        commission = ReferralManager.approve(code, 200, "ORDER-1", 50)
        self.assertEqual(commission, 2.5)
        self.assertEqual(BalanceManager.get_user_balance(100), 2.5)

        # Idempotência: o mesmo pedido não gera uma segunda comissão.
        self.assertEqual(ReferralManager.approve(code, 200, "ORDER-1", 50), 0.0)

    def test_refund_reverses_commission_even_if_balance_was_used(self):
        code = ReferralManager.code_for(100, "João")
        ReferralManager.approve(code, 200, "ORDER-2", 100)
        BalanceManager.use_balance(100, 5.0, reference_id="SPEND")
        self.assertEqual(BalanceManager.get_user_balance(100), 0.0)

        reversed_amount = ReferralManager.reverse("ORDER-2")
        self.assertEqual(reversed_amount, 5.0)
        self.assertEqual(BalanceManager.get_user_balance(100), -5.0)


if __name__ == "__main__":
    unittest.main()
