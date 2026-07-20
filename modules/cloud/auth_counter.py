import asyncio
from functions.database import database as db
from .update_api import get_websocket_manager

async def get_auth_count() -> int:
    """Obtém o número de membros autenticados"""
    try:
        print("🔍 Iniciando verificação de contagem de membros autenticados...")
        
        # Obter configuração do cloud
        cloud_config = db.get_document("cloud_data") or {}
        bot_id = cloud_config.get("client_id")
        
        print(f"📋 Bot ID configurado: {bot_id}")
        
        if not bot_id:
            print("❌ Bot ID não configurado")
            return 0
        
        # Obter WebSocket manager
        ws_manager = get_websocket_manager()
        
        print(f"🔌 WebSocket conectado: {ws_manager.is_connected()}")
        
        if not ws_manager.is_connected():
            print("❌ WebSocket não está conectado")
            return 0
        
        # Fazer requisição para verificar contagem
        print("📤 Enviando requisição check_auth_count...")
        response = await ws_manager.check_auth_count(bot_id)
        
        print(f"📥 Resposta recebida: {response}")
        
        if response.get("success"):
            auth_count = response.get("data", {}).get("count", 0)
            print(f"✅ Contagem obtida: {auth_count} membros autenticados")
            return auth_count
        else:
            print(f"❌ Erro ao obter contagem: {response.get('message', 'Erro desconhecido')}")
            return 0
            
    except Exception as e:
        print(f"❌ Erro ao obter contagem de membros autenticados: {e}")
        import traceback
        traceback.print_exc()
        return 0
