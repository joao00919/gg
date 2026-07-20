"""
Extension Subscription Manager
Manages paid extension subscriptions with Carteira Integrada API integration
"""
import aiohttp
import json
import os
from datetime import datetime, timedelta
from functions.database import database as db

# Carteira Integrada API
ZYNEX_WALLET_API = os.getenv("ZYNEX_WALLET_API_URL", "").strip().rstrip("/")
ZYNEX_WALLET_API_KEY = os.getenv("ZYNEX_WALLET_API_KEY", "").strip()

# Extensões disponíveis para compra
PURCHASABLE_EXTENSIONS = {
    "boost": {
        "name": "Sync Boost",
        "price": 50.00,
        "description": "Sistema de venda de boosts para servidores",
        "duration_days": 30
    }
}


def _get_db_path(extension_id: str = None) -> str:
    """Retorna o caminho do banco de dados baseado na extensão"""
    if extension_id == "boost":
        return "database/extensions/syncboost/subscriptions.json"
    return "database/extensions/subscriptions.json"


def get_subscriptions(extension_id: str = None) -> dict:
    """Obtém todas as assinaturas ativas do arquivo apropriado"""
    return db.obter(_get_db_path(extension_id))


def save_subscriptions(data: dict, extension_id: str = None):
    """Salva dados de assinaturas no arquivo apropriado"""
    db.salvar(_get_db_path(extension_id), data)


def get_extension_subscription(extension_id: str) -> dict:
    """Obtém assinatura de uma extensão específica"""
    subs = get_subscriptions(extension_id)
    return subs.get(extension_id, {})


def is_extension_active(extension_id: str) -> bool:
    """Verifica se uma extensão está ativa (assinatura válida)"""
    sub = get_extension_subscription(extension_id)
    if not sub:
        return False
    
    expires_at = sub.get("expires_at")
    if not expires_at:
        return False
    
    try:
        expiry = datetime.fromisoformat(expires_at)
        return datetime.now() < expiry
    except:
        return False


def get_expiry_date(extension_id: str) -> str:
    """Retorna a data de expiração formatada"""
    sub = get_extension_subscription(extension_id)
    if not sub:
        return None
    
    expires_at = sub.get("expires_at")
    if not expires_at:
        return None
    
    try:
        expiry = datetime.fromisoformat(expires_at)
        return expiry.strftime("%d/%m/%Y às %H:%M")
    except:
        return None


def get_days_remaining(extension_id: str) -> int:
    """Retorna dias restantes da assinatura"""
    sub = get_extension_subscription(extension_id)
    if not sub:
        return 0
    
    expires_at = sub.get("expires_at")
    if not expires_at:
        return 0
    
    try:
        expiry = datetime.fromisoformat(expires_at)
        remaining = (expiry - datetime.now()).days
        return max(0, remaining)
    except:
        return 0


def activate_extension(extension_id: str, payment_id: str):
    """Ativa uma extensão após pagamento confirmado"""
    subs = get_subscriptions(extension_id)
    extension_info = PURCHASABLE_EXTENSIONS.get(extension_id, {})
    duration_days = extension_info.get("duration_days", 30)
    
    # Calcular data de expiração
    now = datetime.now()
    
    # Se já existe assinatura ativa, estender a partir da expiração atual
    if extension_id in subs and is_extension_active(extension_id):
        current_expiry = datetime.fromisoformat(subs[extension_id]["expires_at"])
        expires_at = current_expiry + timedelta(days=duration_days)
    else:
        expires_at = now + timedelta(days=duration_days)
    
    subs[extension_id] = {
        "active": True,
        "activated_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "payment_id": payment_id,
        "payments": subs.get(extension_id, {}).get("payments", []) + [payment_id]
    }
    
    save_subscriptions(subs, extension_id)
    
    # Também ativar na config de extensões
    config = db.obter("configs/config_extensions.json")
    config[extension_id] = True
    db.salvar("configs/config_extensions.json", config)
    
    return expires_at


async def create_payment(extension_id: str, user_id: str) -> dict:
    """Cria um pagamento PIX para a extensão"""
    extension = PURCHASABLE_EXTENSIONS.get(extension_id)
    if not extension:
        return {"success": False, "error": "Extensão não encontrada"}
    if not ZYNEX_WALLET_API or not ZYNEX_WALLET_API_KEY:
        return {"success": False, "error": "Integração de pagamento não configurada"}
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "value": extension["price"],
                "description": f"Assinatura {extension['name']} - 30 dias",
                "coverFee": False
            }
            
            async with session.post(
                f"{ZYNEX_WALLET_API}/payment/create",
                headers={
                    "X-API-Key": ZYNEX_WALLET_API_KEY,
                    "Content-Type": "application/json"
                },
                json=payload
            ) as response:
                data = await response.json()
                
                if data.get("success"):
                    payment_data = data.get("data", {})
                    
                    # Salvar pagamento pendente
                    pending = db.obter("database/extensions/pending_payments.json")
                    pending[payment_data["id"]] = {
                        "extension_id": extension_id,
                        "user_id": user_id,
                        "value": extension["price"],
                        "created_at": datetime.now().isoformat(),
                        "status": "PENDING"
                    }
                    db.salvar("database/extensions/pending_payments.json", pending)
                    
                    return {
                        "success": True,
                        "payment_id": payment_data["id"],
                        "qrcode_url": payment_data.get("qrcodeUrl"),
                        "copy_paste": payment_data.get("copyPaste"),
                        "value": extension["price"]
                    }
                else:
                    return {"success": False, "error": data.get("error", "Erro ao criar pagamento")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_payment_history() -> dict:
    """Obtém histórico de pagamentos realizados"""
    return db.obter("database/extensions/payment_history.json")


def save_payment_history(data: dict):
    """Salva histórico de pagamentos"""
    db.salvar("database/extensions/payment_history.json", data)


def get_user_payments(user_id: str) -> dict:
    """Retorna pagamentos pendentes e histórico do usuário"""
    pending = db.obter("database/extensions/pending_payments.json")
    history = get_payment_history()
    
    user_pending = []
    for p_id, p in pending.items():
        if p.get("user_id") == user_id:
            p["id"] = p_id
            user_pending.append(p)
            
    user_history = []
    for h_id, h in history.items():
        if h.get("user_id") == user_id:
            h["id"] = h_id
            user_history.append(h)
            
    # Ordenar por data (mais recente primeiro)
    user_pending.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    user_history.sort(key=lambda x: x.get("completed_at", ""), reverse=True)
    
    return {"pending": user_pending, "history": user_history}


async def check_payment(payment_id: str) -> dict:
    """Verifica o status de um pagamento"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ZYNEX_WALLET_API}/payment/get/{payment_id}",
                headers={"X-API-Key": ZYNEX_WALLET_API_KEY}
            ) as response:
                data = await response.json()
                
                if data.get("success"):
                    payment_data = data.get("data", {})
                    status = payment_data.get("status", "PENDING")
                    
                    # Se pagamento completado, ativar extensão
                    if status == "COMPLETED":
                        pending = db.obter("database/extensions/pending_payments.json")
                        if payment_id in pending:
                            payment_info = pending[payment_id]
                            extension_id = payment_info["extension_id"]
                            expires_at = activate_extension(extension_id, payment_id)
                            
                            # Salvar no histórico
                            history = get_payment_history()
                            payment_info["status"] = "COMPLETED"
                            payment_info["completed_at"] = datetime.now().isoformat()
                            payment_info["expires_at"] = expires_at.strftime("%d/%m/%Y às %H:%M")
                            history[payment_id] = payment_info
                            save_payment_history(history)
                            
                            # Remover dos pendentes
                            del pending[payment_id]
                            db.salvar("database/extensions/pending_payments.json", pending)
                            
                            return {
                                "success": True,
                                "status": "COMPLETED",
                                "extension_id": extension_id,
                                "expires_at": expires_at.strftime("%d/%m/%Y às %H:%M")
                            }
                    
                    return {
                        "success": True,
                        "status": status
                    }
                else:
                    return {"success": False, "error": data.get("error", "Erro ao verificar pagamento")}
    except Exception as e:
        return {"success": False, "error": str(e)}
