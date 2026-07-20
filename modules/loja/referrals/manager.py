from __future__ import annotations

import re
import time
from typing import Any

from functions.database import database as db
from modules.loja.saldo.balance_manager import BalanceManager

DEFAULT_CONFIG = {
    "enabled": True,
    "prefix": "ZYNEX",
    "commission_percent": 5.0,
    "referred_discount_percent": 5.0,
    "max_uses_per_code": 100,
    "minimum_purchase": 1.0,
}


class ReferralManager:
    @staticmethod
    def get_config() -> dict:
        stored = db.get_document("referral_config") or {}
        return {**DEFAULT_CONFIG, **stored}

    @staticmethod
    def save_config(config: dict) -> None:
        db.save_document("referral_config", {**ReferralManager.get_config(), **config})

    @staticmethod
    def _doc() -> dict:
        data = db.get_document("referrals") or {}
        data.setdefault("codes", {})
        data.setdefault("owners", {})
        data.setdefault("history", [])
        return data

    @staticmethod
    def _save(data: dict) -> None:
        db.save_document("referrals", data)

    @staticmethod
    def code_for(user_id: int, display_name: str = "CLIENTE") -> str:
        data = ReferralManager._doc()
        existing = (data.get("owners") or {}).get(str(user_id))
        if existing:
            return existing
        cfg = ReferralManager.get_config()
        clean = re.sub(r"[^A-Z0-9]", "", str(display_name).upper())[:8] or "CLIENTE"
        base = f"{cfg.get('prefix', 'ZYNEX')}-{clean}{str(user_id)[-3:]}"
        code = base
        index = 2
        while code in data["codes"] and str(data["codes"][code].get("owner_id")) != str(user_id):
            code = f"{base}{index}"
            index += 1
        data["codes"][code] = {
            "code": code,
            "owner_id": int(user_id),
            "created_at": int(time.time()),
            "active": True,
            "uses": 0,
            "approved_uses": 0,
            "total_commission": 0.0,
        }
        data["owners"][str(user_id)] = code
        ReferralManager._save(data)
        return code

    @staticmethod
    def validate(code: str, buyer_id: int, total: float) -> tuple[bool, str, float, dict | None]:
        cfg = ReferralManager.get_config()
        if not cfg.get("enabled", True):
            return False, "Programa de indicação desativado.", 0.0, None
        code = str(code or "").strip().upper()
        data = ReferralManager._doc()
        entry = (data.get("codes") or {}).get(code)
        if not entry or not entry.get("active", True):
            return False, "Código de indicação inválido.", 0.0, None
        if str(entry.get("owner_id")) == str(buyer_id):
            return False, "Você não pode usar o próprio código.", 0.0, None
        if int(entry.get("uses", 0)) >= int(cfg.get("max_uses_per_code", 100)):
            return False, "Esse código atingiu o limite de usos.", 0.0, None
        if float(total or 0) < float(cfg.get("minimum_purchase", 1.0)):
            return False, "O valor da compra é menor que o mínimo do programa.", 0.0, None
        discount = round(float(total) * float(cfg.get("referred_discount_percent", 5.0)) / 100, 2)
        return True, "Código válido.", discount, entry

    @staticmethod
    def register_pending(code: str, buyer_id: int, cart_id: str) -> None:
        data = ReferralManager._doc()
        entry = (data.get("codes") or {}).get(str(code).upper())
        if not entry:
            return
        data["history"].append({
            "type": "pending",
            "code": str(code).upper(),
            "owner_id": entry.get("owner_id"),
            "buyer_id": int(buyer_id),
            "cart_id": str(cart_id),
            "timestamp": int(time.time()),
        })
        ReferralManager._save(data)

    @staticmethod
    def approve(code: str, buyer_id: int, purchase_id: str, paid_value: float) -> float:
        code = str(code or "").upper()
        data = ReferralManager._doc()
        entry = (data.get("codes") or {}).get(code)
        if not entry or str(entry.get("owner_id")) == str(buyer_id):
            return 0.0
        # Idempotência: um pedido não paga comissão duas vezes.
        if any(h.get("type") == "approved" and h.get("purchase_id") == purchase_id for h in data["history"]):
            return 0.0
        cfg = ReferralManager.get_config()
        commission = round(float(paid_value or 0) * float(cfg.get("commission_percent", 5.0)) / 100, 2)
        entry["uses"] = int(entry.get("uses", 0)) + 1
        entry["approved_uses"] = int(entry.get("approved_uses", 0)) + 1
        entry["total_commission"] = round(float(entry.get("total_commission", 0)) + commission, 2)
        data["history"].append({
            "type": "approved",
            "code": code,
            "owner_id": entry.get("owner_id"),
            "buyer_id": int(buyer_id),
            "purchase_id": purchase_id,
            "paid_value": float(paid_value or 0),
            "commission": commission,
            "timestamp": int(time.time()),
            "reversed": False,
        })
        ReferralManager._save(data)
        if commission > 0:
            BalanceManager.add_balance(
                int(entry["owner_id"]),
                commission,
                deposit_id=f"REF-{purchase_id}",
                payment_method="referral",
            )
        return commission

    @staticmethod
    def reverse(purchase_id: str) -> float:
        data = ReferralManager._doc()
        target = next((h for h in data["history"] if h.get("type") == "approved" and h.get("purchase_id") == purchase_id and not h.get("reversed")), None)
        if not target:
            return 0.0
        amount = float(target.get("commission", 0))
        owner_id = int(target.get("owner_id"))
        if amount > 0:
            BalanceManager.adjust_balance(
                owner_id,
                -amount,
                reference_id=f"REFUND-{purchase_id}",
                description="Estorno de comissão por reembolso",
            )
        target["reversed"] = True
        target["reversed_at"] = int(time.time())
        code = target.get("code")
        entry = (data.get("codes") or {}).get(code, {})
        entry["approved_uses"] = max(0, int(entry.get("approved_uses", 0)) - 1)
        entry["total_commission"] = max(0.0, round(float(entry.get("total_commission", 0)) - amount, 2))
        data["history"].append({"type": "reversed", "purchase_id": purchase_id, "commission": amount, "timestamp": int(time.time())})
        ReferralManager._save(data)
        return amount

    @staticmethod
    def ranking(limit: int = 10) -> list[dict[str, Any]]:
        data = ReferralManager._doc()
        return sorted((data.get("codes") or {}).values(), key=lambda x: float(x.get("total_commission", 0)), reverse=True)[:limit]
