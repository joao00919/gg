"""
Sistema de gerenciamento de histórico de compras
Armazena dados detalhados de cada compra para métricas e estatísticas
"""
import disnake
from functions.database import database as db
from typing import Dict, List, Optional
import random
import string
import asyncio
import threading
from functions.email_utils import send_notification_email


class PurchaseManager:
    """Gerencia o histórico de compras dos clientes"""
    _lock = threading.RLock()
    
    @staticmethod
    def _generate_purchase_id(length: int = 12) -> str:
        """Gera um ID único para a compra"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    @staticmethod
    def _load_purchases() -> dict:
        """Carrega o arquivo de compras"""
        data = db.get_document("loja_buys")
        if not data:
            data = {"purchases": {}}
        if "purchases" not in data:
            data["purchases"] = {}
        return data
    
    @staticmethod
    def _save_purchases(data: dict):
        """Salva o arquivo de compras"""
        db.save_document("loja_buys", data)
    
    @staticmethod
    def _same_user(value, user_id: int) -> bool:
        try:
            return str(int(value)) == str(int(user_id))
        except (TypeError, ValueError):
            return str(value) == str(user_id)

    @staticmethod
    def _existing_purchase_for_cart(data: dict, cart_id: str, product_id: str, field_id: str) -> Optional[Dict]:
        expected = f"cart:{cart_id}:{product_id}:{field_id}"
        for purchases in (data.get("purchases") or {}).values():
            for purchase in purchases or []:
                metadata = purchase.get("metadata") or {}
                if str(metadata.get("idempotency_key") or "") == expected:
                    return purchase
                if (
                    str(metadata.get("cart_id") or "") == str(cart_id)
                    and str((purchase.get("product") or {}).get("id") or "") == str(product_id)
                    and str((purchase.get("field") or {}).get("id") or "") == str(field_id)
                ):
                    return purchase
        return None

    @staticmethod
    def repair_user_purchase_history(user_id: int) -> int:
        """Recupera pedidos aprovados que ficaram no carrinho sem entrar no histórico.

        O reparo é idempotente e cobre pagamentos PIX, saldo e versões antigas do
        checkout. Isso garante que o seletor de compras do ticket use a mesma fonte
        de verdade do restante da loja.
        """
        repaired = 0
        try:
            loja_data = db.get_document("loja_data") or {}
            products = db.get_document("loja_products") or {}
            completed_statuses = {"approved", "paid", "completed", "paid_with_balance", "delivered", "success", "succeeded", "finished", "complete", "manual_delivery"}
            for cart_id, cart in (loja_data.get("carts") or {}).items():
                cart_user_id = (
                    cart.get("user_id") or cart.get("userId") or cart.get("buyer_id")
                    or cart.get("customer_id") or (cart.get("buyer") or {}).get("id")
                    or (cart.get("customer") or {}).get("id")
                )
                if not PurchaseManager._same_user(cart_user_id, user_id):
                    continue
                if str(cart.get("status") or "").lower() not in completed_statuses:
                    continue
                items = cart.get("items") or []
                if not items and cart.get("product_id"):
                    items = [{
                        "product_id": cart.get("product_id"),
                        "campo_id": cart.get("campo_id") or cart.get("field_id") or "default",
                        "quantity": cart.get("quantity", 1),
                        "price_per_unit": cart.get("price_per_unit") or cart.get("unit_price") or cart.get("total_price", 0),
                        "item_total": cart.get("total_price", 0),
                    }]
                total_cart = float(cart.get("total_price") or sum(float(item.get("item_total") or 0) for item in items) or 0)
                discount = float(cart.get("discount_amount") or 0)
                current = PurchaseManager._load_purchases()
                for item in items:
                    product_id = str(item.get("product_id") or "")
                    field_id = str(item.get("campo_id") or item.get("field_id") or "default")
                    if not product_id:
                        continue
                    if PurchaseManager._existing_purchase_for_cart(current, str(cart_id), product_id, field_id):
                        continue
                    product = products.get(product_id) or {}
                    field = (product.get("campos") or {}).get(field_id) or {}
                    quantity = max(1, int(item.get("quantity") or 1))
                    unit_price = float(item.get("price_per_unit") or 0)
                    item_total = float(item.get("item_total") or (unit_price * quantity))
                    item_discount = (discount * item_total / total_cart) if total_cart > 0 else 0
                    purchase_id = PurchaseManager.register_purchase(
                        user_id=int(user_id),
                        product_id=product_id,
                        product_name=product.get("name") or item.get("product_name") or "Produto",
                        field_id=field_id,
                        field_name=field.get("name") or item.get("campo_name") or item.get("field_name") or "Padrão",
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=item_total,
                        discount_amount=item_discount,
                        final_price=max(0.0, item_total - item_discount),
                        payment_method=cart.get("payment_method") or "PIX",
                        coupon_code=cart.get("coupon_code"),
                        items_received=[],
                        metadata={
                            "cart_id": str(cart_id),
                            "thread_id": cart.get("thread_id"),
                            "guild_id": cart.get("guild_id"),
                            "delivery_type": (product.get("info") or {}).get("delivery_type", cart.get("delivery_type") or "automatic"),
                            "review_enabled": True,
                            "recovered_from_cart": True,
                            "approved_at": cart.get("approved_at") or cart.get("updated_at"),
                        },
                    )
                    if purchase_id:
                        repaired += 1
                        current = PurchaseManager._load_purchases()
        except Exception as exc:
            print(f"[Compras] Não foi possível reparar o histórico do usuário {user_id}: {exc}")
        return repaired

    @staticmethod
    def update_purchase(purchase_id: str, changes: Dict) -> bool:
        """Mescla campos em uma compra já registrada."""
        def merge(target: dict, source: dict) -> dict:
            for key, value in source.items():
                if isinstance(value, dict) and isinstance(target.get(key), dict):
                    merge(target[key], value)
                else:
                    target[key] = value
            return target

        with PurchaseManager._lock:
            data = PurchaseManager._load_purchases()
            for user_id, purchases in (data.get("purchases") or {}).items():
                for purchase in purchases or []:
                    if str(purchase.get("purchase_id")) == str(purchase_id):
                        merge(purchase, dict(changes or {}))
                        purchase.setdefault("user_id", str(user_id))
                        PurchaseManager._save_purchases(data)
                        return True
        return False

    @staticmethod
    def register_purchase(
        user_id: int,
        product_id: str,
        product_name: str,
        field_id: str,
        field_name: str,
        quantity: int,
        unit_price: float,
        total_price: float,
        discount_amount: float,
        final_price: float,
        payment_method: str,
        coupon_code: Optional[str] = None,
        items_received: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Registra uma compra de forma idempotente quando há identificador do pedido/pagamento."""
        metadata = dict(metadata or {})
        idempotency_key = metadata.get("idempotency_key") or metadata.get("payment_id")
        if not idempotency_key and metadata.get("cart_id"):
            idempotency_key = f"cart:{metadata['cart_id']}:{product_id}:{field_id}"
        if idempotency_key:
            metadata["idempotency_key"] = str(idempotency_key)

        with PurchaseManager._lock:
            data = PurchaseManager._load_purchases()
            if idempotency_key:
                for purchases in data["purchases"].values():
                    for purchase in purchases:
                        if str((purchase.get("metadata") or {}).get("idempotency_key")) == str(idempotency_key):
                            return str(purchase["purchase_id"])

            purchase_id = PurchaseManager._generate_purchase_id()
            used_ids = {p.get("purchase_id") for purchases in data["purchases"].values() for p in purchases}
            while purchase_id in used_ids:
                purchase_id = PurchaseManager._generate_purchase_id()

            timestamp = int(disnake.utils.utcnow().timestamp())
            purchase_record = {
                "purchase_id": purchase_id,
                "user_id": str(user_id),
                "timestamp": timestamp,
                "status": "completed",
                "product": {"id": product_id, "name": product_name},
                "field": {"id": field_id, "name": field_name},
                "quantity": max(1, int(quantity)),
                "pricing": {
                    "unit_price": float(unit_price),
                    "total_price": float(total_price),
                    "discount_amount": max(0.0, float(discount_amount)),
                    "final_price": max(0.0, float(final_price)),
                },
                "payment": {"method": payment_method, "coupon_code": coupon_code},
                "delivery": {
                    "items": list(items_received or []),
                    "items_count": len(items_received or []),
                    "delivered_at": timestamp,
                },
                "metadata": metadata,
            }
            user_id_str = str(user_id)
            data["purchases"].setdefault(user_id_str, []).append(purchase_record)
            PurchaseManager._save_purchases(data)

        try:
            from functions.loyalty import award_purchase_points
            award_purchase_points(purchase_id, user_id, float(final_price))
        except Exception as exc:
            print(f"Erro ao atualizar fidelidade: {exc}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(PurchaseManager._send_purchase_email_notification(purchase_record, user_id))
        except RuntimeError:
            pass

        return purchase_id

    @staticmethod
    async def _send_purchase_email_notification(purchase: dict, user_id: int):
        """Envia uma notificação de venda por email"""
        try:
            product_name = purchase.get("product", {}).get("name")
            quantity = purchase.get("quantity")
            final_price = purchase.get("pricing", {}).get("final_price")
            method = purchase.get("payment", {}).get("method")
            purchase_id = purchase.get("purchase_id")
            
            subject = f"Nova Venda: {product_name} - ID {purchase_id}"
            
            body_text = (
                f"Nova venda realizada no seu bot!\n\n"
                f"Produto: {product_name}\n"
                f"Quantidade: {quantity}\n"
                f"Valor Pago: R$ {final_price:.2f}\n"
                f"Método: {method}\n"
                f"ID da Compra: {purchase_id}\n"
                f"ID do Usuário: {user_id}\n"
            )
            
            body_html = f"""
            <html>
            <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #5c5ef0; border-bottom: 2px solid #5c5ef0; padding-bottom: 10px;">Nova Venda Realizada!</h2>
                    <p>Uma nova venda foi processada com sucesso no seu bot.</p>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Produto:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{product_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Quantidade:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{quantity}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Valor Pago:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">R$ {final_price:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Método:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{method}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>ID da Compra:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><code>{purchase_id}</code></td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>ID do Usuário:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><code>{user_id}</code></td>
                        </tr>
                    </table>
                    <p style="margin-top: 20px; font-size: 0.9em; color: #777;">
                        Esta é uma notificação automática do seu sistema de vendas.
                    </p>
                </div>
            </body>
            </html>
            """
            
            await send_notification_email(subject, body_text, body_html)
        except Exception as e:
            print(f"Erro ao processar notificação de email: {e}")
    
    @staticmethod
    def register_generic_payment(
        user_id: int,
        amount: float,
        payment_method: str,
        description: Optional[str] = None,
        payment_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Registra um pagamento genérico (sem produto específico) no histórico
        
        Args:
            user_id: ID do usuário que pagou
            amount: Valor pago
            payment_method: Método de pagamento usado
            description: Descrição do pagamento
            payment_id: ID do pagamento (opcional)
            metadata: Dados adicionais (opcional)
        
        Returns:
            str: ID da compra registrada
        """
        return PurchaseManager.register_purchase(
            user_id=user_id,
            product_id="generic_payment",
            product_name=description or "Pagamento Genérico",
            field_id="none",
            field_name="Pagamento",
            quantity=1,
            unit_price=amount,
            total_price=amount,
            discount_amount=0.0,
            final_price=amount,
            payment_method=payment_method,
            coupon_code=None,
            items_received=[],
            metadata={
                **(metadata or {}),
                "is_generic_payment": True,
                "payment_id": payment_id
            }
        )
    
    @staticmethod
    def get_user_purchases(user_id: int, limit: Optional[int] = None) -> List[Dict]:
        """
        Obtém o histórico de compras de um usuário
        
        Args:
            user_id: ID do usuário
            limit: Limite de compras a retornar (mais recentes primeiro)
        
        Returns:
            List[Dict]: Lista de compras do usuário
        """
        # Antes da leitura, recupera carrinhos aprovados que versões antigas não
        # registraram em loja_buys. O processo é idempotente.
        PurchaseManager.repair_user_purchase_history(user_id)
        data = PurchaseManager._load_purchases()
        user_id_str = str(user_id)

        purchases = []
        seen = set()
        for storage_user_id, stored in (data.get("purchases") or {}).items():
            for purchase in stored or []:
                record_user = purchase.get("user_id", storage_user_id)
                if not PurchaseManager._same_user(record_user, user_id):
                    continue
                purchase_id = str(purchase.get("purchase_id") or "")
                if purchase_id and purchase_id in seen:
                    continue
                copy_record = purchase.copy()
                copy_record.setdefault("user_id", user_id_str)
                purchases.append(copy_record)
                if purchase_id:
                    seen.add(purchase_id)

        # Somente compras confirmadas e não estornadas aparecem em tickets.
        valid_statuses = {"completed", "approved", "paid", "delivered", "manual_delivery", "success", "succeeded", "finished", "complete", "paid_with_balance"}
        purchases = [
            item for item in purchases
            if str(item.get("status") or "completed").lower() in valid_statuses
            and not bool((item.get("metadata") or {}).get("refunded"))
        ]
        purchases_sorted = sorted(purchases, key=lambda x: x.get("timestamp", 0), reverse=True)

        if limit:
            return purchases_sorted[:limit]
        return purchases_sorted
    
    @staticmethod
    def get_purchase_by_id(purchase_id: str) -> Optional[Dict]:
        """
        Busca uma compra específica pelo ID
        
        Args:
            purchase_id: ID da compra
        
        Returns:
            Optional[Dict]: Dados da compra ou None se não encontrada
        """
        data = PurchaseManager._load_purchases()
        
        for user_id, user_purchases in data["purchases"].items():
            for purchase in user_purchases:
                if purchase.get("purchase_id") == purchase_id:
                    result = purchase.copy()
                    result.setdefault("user_id", str(user_id))
                    return result
        
        return None
    
    @staticmethod
    def get_all_purchases(limit: Optional[int] = None) -> List[Dict]:
        """
        Obtém todas as compras do sistema
        
        Args:
            limit: Limite de compras a retornar (mais recentes primeiro)
        
        Returns:
            List[Dict]: Lista de todas as compras
        """
        data = PurchaseManager._load_purchases()
        
        all_purchases = []
        for user_id, purchases in data["purchases"].items():
            for purchase in purchases:
                purchase_copy = purchase.copy()
                purchase_copy["user_id"] = user_id
                all_purchases.append(purchase_copy)
        
        # Ordenar por timestamp (mais recente primeiro)
        all_purchases_sorted = sorted(all_purchases, key=lambda x: x.get("timestamp", 0), reverse=True)
        
        if limit:
            return all_purchases_sorted[:limit]
        
        return all_purchases_sorted
    
    @staticmethod
    def get_product_purchases(product_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Obtém todas as compras de um produto específico
        
        Args:
            product_id: ID do produto
            limit: Limite de compras a retornar
        
        Returns:
            List[Dict]: Lista de compras do produto
        """
        data = PurchaseManager._load_purchases()
        
        product_purchases = []
        for user_id, purchases in data["purchases"].items():
            for purchase in purchases:
                if purchase.get("product", {}).get("id") == product_id:
                    purchase_copy = purchase.copy()
                    purchase_copy["user_id"] = user_id
                    product_purchases.append(purchase_copy)
        
        # Ordenar por timestamp (mais recente primeiro)
        product_purchases_sorted = sorted(product_purchases, key=lambda x: x.get("timestamp", 0), reverse=True)
        
        if limit:
            return product_purchases_sorted[:limit]
        
        return product_purchases_sorted
    
    @staticmethod
    def get_statistics() -> Dict:
        """
        Calcula estatísticas gerais de vendas
        
        Returns:
            Dict: Estatísticas de vendas
        """
        data = PurchaseManager._load_purchases()
        
        total_purchases = 0
        total_revenue = 0.0
        total_items_sold = 0
        payment_methods = {}
        products_sold = {}
        
        for purchases in data["purchases"].values():
            for purchase in purchases:
                total_purchases += 1
                total_revenue += purchase.get("pricing", {}).get("final_price", 0.0)
                total_items_sold += purchase.get("quantity", 0)
                
                # Contar métodos de pagamento
                method = purchase.get("payment", {}).get("method", "unknown")
                payment_methods[method] = payment_methods.get(method, 0) + 1
                
                # Contar produtos vendidos (incluindo pagamentos genéricos)
                product_id = purchase.get("product", {}).get("id", "unknown")
                product_name = purchase.get("product", {}).get("name", "Unknown")
                
                if product_id not in products_sold:
                    products_sold[product_id] = {
                        "name": product_name,
                        "count": 0,
                        "revenue": 0.0
                    }
                products_sold[product_id]["count"] += 1
                products_sold[product_id]["revenue"] += purchase.get("pricing", {}).get("final_price", 0.0)
        
        return {
            "total_purchases": total_purchases,
            "total_revenue": total_revenue,
            "total_items_sold": total_items_sold,
            "unique_customers": len(data["purchases"]),
            "average_ticket": total_revenue / total_purchases if total_purchases > 0 else 0.0,
            "payment_methods": payment_methods,
            "products_sold": products_sold
        }
    
    @staticmethod
    def get_user_statistics(user_id: int) -> Dict:
        """
        Calcula estatísticas de compras de um usuário específico
        
        Args:
            user_id: ID do usuário
        
        Returns:
            Dict: Estatísticas do usuário
        """
        purchases = PurchaseManager.get_user_purchases(user_id)
        
        total_spent = 0.0
        total_items = 0
        products_bought = {}
        
        for purchase in purchases:
            total_spent += purchase.get("pricing", {}).get("final_price", 0.0)
            total_items += purchase.get("quantity", 0)
            
            product_id = purchase.get("product", {}).get("id", "unknown")
            if product_id not in products_bought:
                products_bought[product_id] = {
                    "name": purchase.get("product", {}).get("name", "Unknown"),
                    "count": 0,
                    "spent": 0.0
                }
            products_bought[product_id]["count"] += 1
            products_bought[product_id]["spent"] += purchase.get("pricing", {}).get("final_price", 0.0)
        
        return {
            "total_purchases": len(purchases),
            "total_spent": total_spent,
            "total_items": total_items,
            "products_bought": products_bought,
            "first_purchase": purchases[-1].get("timestamp") if purchases else None,
            "last_purchase": purchases[0].get("timestamp") if purchases else None
        }
