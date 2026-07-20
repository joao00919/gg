from __future__ import annotations

from datetime import datetime, timezone
import threading

from functions.database import database as db
from modules.loja.cart.purchase_manager import PurchaseManager

_LOCK = threading.RLock()


def save_purchase_review(*, purchase_id: str, user_id: int | str, rating: int, comment: str = "", image_url: str | None = None) -> dict:
    if int(rating) not in range(1, 6):
        raise ValueError("A nota deve estar entre 1 e 5.")
    purchase = PurchaseManager.get_purchase_by_id(str(purchase_id))
    if not purchase:
        raise ValueError("Compra não encontrada.")
    purchase_user = str(purchase.get("user_id") or purchase.get("metadata", {}).get("user_id") or "")
    if purchase_user and purchase_user != str(user_id):
        raise PermissionError("A compra não pertence ao usuário.")
    with _LOCK:
        raw = db.get_document("loja_reviews")
        document = {"version": 1, "items": raw} if isinstance(raw, list) else (raw or {"version": 1, "items": []})
        items = document.setdefault("items", [])
        now = datetime.now(timezone.utc).isoformat()
        review = next((item for item in items if item.get("purchaseId") == str(purchase_id)), None)
        payload = {
            "purchaseId": str(purchase_id),
            "userId": str(user_id),
            "productId": str(purchase.get("product", {}).get("id", "")),
            "rating": int(rating),
            "comment": str(comment)[:1000],
            "imageUrl": image_url,
            "verified": True,
            "updatedAt": now,
        }
        if review:
            review.update(payload)
        else:
            payload["createdAt"] = now
            items.append(payload)
            review = payload
        document["items"] = items
        db.save_document("loja_reviews", document)
        _update_product_rating(payload["productId"], items)
        return dict(review)


def _update_product_rating(product_id: str, reviews: list[dict]) -> None:
    if not product_id:
        return
    valid = [item for item in reviews if item.get("productId") == product_id and item.get("verified")]
    products = db.get_document("loja_products") or {}
    product = products.get(product_id)
    if not product:
        return
    product["rating_average"] = round(sum(int(item["rating"]) for item in valid) / len(valid), 2) if valid else 0.0
    product["rating_count"] = len(valid)
    products[product_id] = product
    db.save_document("loja_products", products)


def save_ticket_review(*, ticket_id: int | str, user_id: int | str, staff_id: int | str | None, category: str | None, rating: int, comment: str = "") -> dict:
    if int(rating) not in range(1, 6):
        raise ValueError("A nota deve estar entre 1 e 5.")
    with _LOCK:
        raw = db.get_document("ticket_reviews")
        document = {"version": 1, "items": raw} if isinstance(raw, list) else (raw or {"version": 1, "items": []})
        items = document.setdefault("items", [])
        if any(item.get("ticketId") == str(ticket_id) for item in items):
            raise ValueError("Este ticket já foi avaliado.")
        review = {
            "ticketId": str(ticket_id), "userId": str(user_id),
            "staffId": str(staff_id) if staff_id is not None else None,
            "category": category, "rating": int(rating), "comment": str(comment)[:1000],
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        items.append(review)
        document["items"] = items
        db.save_document("ticket_reviews", document)
        return review
