import aiohttp
import asyncio
import logging
import json

# O módulo Cloud depende da interface Socket.IO completa (set_bot,
# set_callbacks, check_auth_count, register_bot etc.). O gerenciador genérico
# de ``connections`` não implementa esse contrato; portanto, ele só é usado
# quando realmente for compatível.
try:
    from connections import get_manager as _get_ws_manager
except ImportError:
    try:
        from bot.connections import get_manager as _get_ws_manager
    except ImportError:
        def _get_ws_manager():
            return None

from .websocket_manager import WebSocketManager as CloudWSManager

# Instância global do gerenciador WebSocket
websocket_manager = None
logger = logging.getLogger(__name__)

def _supports_cloud_contract(manager) -> bool:
    required = (
        "set_bot",
        "set_callbacks",
        "start",
        "stop",
        "is_connected",
        "check_auth_count",
        "check_user_verification",
        "register_bot",
    )
    return manager is not None and all(hasattr(manager, name) for name in required)


def get_websocket_manager():
    """Retorna um gerenciador compatível com todos os recursos do ZYNEX Cloud."""
    global websocket_manager

    if not _supports_cloud_contract(websocket_manager):
        candidate = None
        try:
            candidate = _get_ws_manager()
        except Exception:
            candidate = None

        websocket_manager = (
            candidate if _supports_cloud_contract(candidate) else CloudWSManager()
        )

    bot_instance = get_bot_instance()
    if bot_instance and getattr(websocket_manager, "bot", None) is not bot_instance:
        websocket_manager.set_bot(bot_instance)

    return websocket_manager

def _get_http_base_url() -> str:
    """Obtém a URL base para chamadas HTTP da Sync Cloud API.
    Usa o config_api.json como fonte principal.
    """
    try:
        from .cloud_config import get_cloud_url
        return get_cloud_url()
    except Exception:
        # Fallback para config antigo
        try:
            from functions.database import database as db
            config = db.obter("configs/config_websocket.json") or {}
            websocket_cfg = (config.get("websocket_cloud") or {})
            http_cfg = (config.get("http") or {})
            return (
                websocket_cfg.get("http_url")
                or http_cfg.get("server_url")
                or websocket_cfg.get("server_url")
                or "https://cloud.zynxapplications.com.br"
            )
        except Exception:
            return "https://cloud.zynxapplications.com.br"

async def initialize_websocket():
    """Inicializa o WebSocket automaticamente se configurado"""
    from functions.database import database as db
    config = db.obter("configs/config_websocket.json")
    websocket_config = config.get("websocket_cloud", {})
    
    auto_start = websocket_config.get("auto_start", False)
    if not auto_start:
        logger.info("WebSocket auto-start desabilitado nas configurações")
        return
    
    try:
        # Aguardar um pouco para garantir que o bot está totalmente pronto
        logger.info("[CloudWebSocket] Aguardando bot estar totalmente pronto antes de conectar...")
        await asyncio.sleep(3)  # Aguardar 3 segundos antes de tentar conectar
        
        ws_manager = get_websocket_manager()
        
        # Verificar se já está conectado antes de tentar iniciar novamente
        if ws_manager.connected:
            logger.info("[CloudWebSocket] WebSocket já está conectado, pulando inicialização")
            return
        
        # Definir bot no WebSocketManager se disponível
        bot_instance = get_bot_instance()
        if bot_instance:
            ws_manager.set_bot(bot_instance)
            # Aguardar um pouco mais para garantir que o bot está totalmente configurado
            await asyncio.sleep(1)
        
        # Configurar callbacks
        async def on_connect():
            logger.info("[CloudWebSocket] WebSocket conectado com sucesso!")
        
        async def on_disconnect():
            # Não logar como warning - o WebSocketManager já cuida disso
            # Apenas logar como debug para não poluir os logs
            logger.debug("[CloudWebSocket] WebSocket desconectado - loop de reconexão ativo")
        
        async def on_error(e):
            logger.error(f"[CloudWebSocket] Erro no WebSocket: {e}")
        
        async def on_message(message_data):
            event = message_data.get('event')
            data = message_data.get('data', {})
            
            if event == 'auth_log':
                await process_auth_log(data)
            elif event == 'redeem_gift':
                await process_redeem_gift(data)
            elif event == 'recover_members':
                await process_recover_members(data)
            elif event == 'remove_verified_role':
                await process_remove_verified_role(data)
        
        ws_manager.set_callbacks(
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            on_error=on_error,
            on_message=on_message
        )
        
        # Iniciar conexão
        logger.info("[CloudWebSocket] Iniciando conexão WebSocket...")
        await ws_manager.start()
        logger.info("[CloudWebSocket] WebSocket inicializado automaticamente")
        
    except Exception as e:
        logger.error(f"[CloudWebSocket] Erro ao inicializar WebSocket: {e}")
        import traceback
        traceback.print_exc()

def register_websocket_callbacks():
    """Registra callbacks de mensagens/desconexão/erro no WebSocket já conectado (não inicia conexão)."""
    try:
        ws_manager = get_websocket_manager()

        # Definir bot no WebSocketManager se disponível
        bot_instance = get_bot_instance()
        if bot_instance:
            ws_manager.set_bot(bot_instance)

        async def on_connect():
            logger.info("[CloudWebSocket] WebSocket callbacks registrados e conexão ativa!")

        async def on_disconnect():
            # Não logar como warning - o WebSocketManager já cuida disso
            # Apenas logar como debug para não poluir os logs
            logger.debug("[CloudWebSocket] WebSocket desconectado - loop de reconexão ativo")

        async def on_error(e):
            logger.error(f"[CloudWebSocket] Erro no WebSocket: {e}")

        async def on_message(message_data):
            event = message_data.get('event')
            data = message_data.get('data', {})
            
            logger.info(f"[DEBUG] on_message callback called with event: {event}")

            if event == 'auth_log':
                logger.info(f"[DEBUG] Processing auth_log event in callback")
                await process_auth_log(data)
            elif event == 'redeem_gift':
                await process_redeem_gift(data)
            elif event == 'recover_members':
                await process_recover_members(data)
            elif event == 'remove_verified_role':
                await process_remove_verified_role(data)

        ws_manager.set_callbacks(
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            on_error=on_error,
            on_message=on_message
        )
    except Exception as e:
        logger.error(f"[CloudWebSocket] Erro ao registrar callbacks do WebSocket: {e}")

async def stop_websocket():
    """Para o WebSocket"""
    global websocket_manager
    if websocket_manager:
        await websocket_manager.stop()
        logger.info("[CloudWebSocket] WebSocket parado")

async def process_auth_log(auth_data: dict):
    """Processa log de autenticação recebido via WebSocket com timeout"""
    try:
        # Adicionar timeout para não bloquear indefinidamente
        await asyncio.wait_for(_process_auth_log_internal(auth_data), timeout=30.0)
    except asyncio.TimeoutError:
        logger.error("❌ Timeout ao processar log de auth (30s)")
    except Exception as e:
        logger.error(f"❌ Erro ao processar log de auth: {e}")
        import traceback
        traceback.print_exc()

async def _process_auth_log_internal(auth_data: dict):
    """Processamento interno do log de autenticação"""
    try:
        # Usar o mesmo sistema de detecção de duplicação do auth_logs.py
        # Criar identificador único usando o mesmo formato do auth_logs.py
        user_data = auth_data.get("user", {})
        user_id = user_data.get("id")
        verified_at = user_data.get("verified_at")
        unverified_at = user_data.get("unverified_at")
        
        # Identificar tipo de evento (verificação ou revogação) - mesmo formato do auth_logs.py
        is_revocation = unverified_at is not None
        event_type = "revoke" if is_revocation else "verify"
        
        # Usar timestamp específico do evento para identificar o log - mesmo formato do auth_logs.py
        from datetime import datetime
        timestamp = unverified_at if is_revocation else (verified_at or datetime.now().isoformat())
        log_id = f"{user_id}_{event_type}_{timestamp}"
        
        # Verificar se já foi processado (usando variável global compartilhada)
        if not hasattr(process_auth_log, '_processing'):
            process_auth_log._processing = set()
        
        if log_id in process_auth_log._processing:
            logger.info(f"[AUTH_LOG] Processamento duplicado ignorado: {log_id}")
            return
        
        # Adicionar à lista de processamentos ANTES de processar (evitar race condition)
        process_auth_log._processing.add(log_id)
        
        # Limpar processamentos antigos (manter apenas os últimos 100)
        if len(process_auth_log._processing) > 100:
            process_list = list(process_auth_log._processing)
            process_auth_log._processing.clear()
            process_auth_log._processing.update(process_list[-50:])
        
        logger.info(f"🔍 [AUTH_LOG] Dados recebidos: {auth_data}")
        
        from . import auth_logs
        
        # Obter instância do bot (precisamos de uma forma de acessar o bot)
        # Por enquanto, vamos usar uma abordagem global
        bot_instance = get_bot_instance()
        if bot_instance:
            logger.info(f"[AUTH_LOG] Bot instance encontrada")
            
            # Enviar log de auth com timeout
            try:
                success, message = await asyncio.wait_for(
                    auth_logs.send_auth_log(bot_instance, auth_data),
                    timeout=15.0
                )
                if success:
                    logger.info(f"Log de auth enviado: {message}")
                else:
                    logger.error(f"Erro ao enviar log de auth: {message}")
            except asyncio.TimeoutError:
                logger.error("❌ Timeout ao enviar log de auth (15s)")
            except Exception as e:
                logger.error(f"❌ Erro ao enviar log de auth: {e}")
            
            # Verificar se é verificação ou desverificação com timeout
            try:
                if auth_data.get("success") and "unverified_at" not in auth_data.get("user", {}):
                    # Verificação bem-sucedida - dar cargo
                    logger.info(f"[AUTH_LOG] Verificação bem-sucedida, tentando dar cargo de verificado...")
                    await asyncio.wait_for(
                        give_verified_role(bot_instance, auth_data),
                        timeout=15.0
                    )
                elif not auth_data.get("success") or "unverified_at" in auth_data.get("user", {}):
                    # Desverificação ou falha - remover cargo
                    logger.info(f"[AUTH_LOG] Desverificação detectada, tentando remover cargo de verificado...")
                    await asyncio.wait_for(
                        remove_verified_role(bot_instance, auth_data),
                        timeout=15.0
                    )
                else:
                    logger.warning(f"[AUTH_LOG] Status de verificação não reconhecido")
            except asyncio.TimeoutError:
                logger.error("❌ Timeout ao processar cargo (15s)")
            except Exception as e:
                logger.error(f"❌ Erro ao processar cargo: {e}")
        else:
            logger.warning("Instância do bot não disponível para enviar log de auth")
            # Remover da lista de processamentos se não conseguiu processar
            process_auth_log._processing.discard(log_id)
            
    except Exception as e:
        logger.error(f"Erro ao processar log de auth: {e}")
        import traceback
        traceback.print_exc()
        # Em caso de erro, remover da lista para permitir nova tentativa
        try:
            user_data = auth_data.get("user", {})
            user_id = user_data.get("id")
            verified_at = user_data.get("verified_at")
            unverified_at = user_data.get("unverified_at")
            is_revocation = unverified_at is not None
            event_type = "revoke" if is_revocation else "verify"
            from datetime import datetime
            timestamp = unverified_at if is_revocation else (verified_at or datetime.now().isoformat())
            log_id = f"{user_id}_{event_type}_{timestamp}"
            if hasattr(process_auth_log, '_processing'):
                process_auth_log._processing.discard(log_id)
        except Exception:
            pass

async def give_verified_role(bot, auth_data: dict):
    """Dá o cargo de verificado para o usuário com retry logic"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            await _give_verified_role_internal(bot, auth_data)
            return  # Sucesso, sair do loop
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"[GIVE_ROLE] Tentativa {attempt + 1}/{max_retries} falhou: {e}, tentando novamente...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"[GIVE_ROLE] Todas as tentativas falharam: {e}")
                raise

async def _give_verified_role_internal(bot, auth_data: dict):
    """Processamento interno de dar cargo"""
    try:
        logger.info(f"[GIVE_ROLE] Iniciando processo de dar cargo de verificado...")
        
        from functions.database import database as db
        
        user_data = auth_data.get("user", {})
        user_id = user_data.get("id")
        guild_id = auth_data.get("guild_id")
        
        if not user_id or not guild_id:
            logger.warning("Dados insuficientes para dar cargo de verificado")
            return
        
        # Obter ID do cargo de verificado
        cargos_config = db.get_document("cargos") or {}
        verified_role_id = cargos_config.get("cargo_verificado")
        
        if not verified_role_id:
            logger.warning("Cargo de verificado não configurado")
            return
        
        # Obter servidor e usuário
        guild = bot.get_guild(int(guild_id))
        if not guild:
            logger.warning(f"Servidor {guild_id} não encontrado")
            return
        
        try:
            member = await guild.fetch_member(int(user_id))
        except Exception:
            logger.warning(f"Membro {user_id} não encontrado no servidor {guild_id}")
            return
        
        # Obter cargo
        verified_role = guild.get_role(int(verified_role_id))
        if not verified_role:
            logger.warning(f"Cargo de verificado {verified_role_id} não encontrado")
            return
        
        # Verificar se o usuário já tem o cargo
        already_has_role = verified_role in member.roles
        
        # Dar o cargo se ainda não tiver
        if not already_has_role:
            await member.add_roles(verified_role, reason="Verificação automática via SyncCloud")
            logger.info(f"Cargo de verificado dado para {member.name} ({user_id}) no servidor {guild.name}")
        else:
            logger.info(f"Usuário {member.name} já tem o cargo de verificado")

        # Lógica para remover cargo de autorole (sempre verificar, mesmo se já tinha o cargo)
        cloud_config = db.get_document("cloud_data") or {}
        definitions = cloud_config.get("definitions", {})
        if definitions.get("remove_autorole", {}).get("enabled", False):
            logger.info(f"[REMOVE_AUTOROLE] Definição 'remove_autorole' está ativa.")
            cargos_config_autorole = db.get_document("cargos") or {}
            autorole_id = cargos_config_autorole.get("cargo_auto_role")
            
            if not autorole_id:
                logger.warning("[REMOVE_AUTOROLE] Cargo de autorole não configurado.")
            else:
                autorole = guild.get_role(int(autorole_id))
                if not autorole:
                    logger.warning(f"[REMOVE_AUTOROLE] Cargo de autorole {autorole_id} não encontrado no servidor.")
                elif autorole in member.roles:
                    try:
                        await member.remove_roles(autorole, reason="Remoção de autorole após verificação via SyncCloud")
                        logger.info(f"[REMOVE_AUTOROLE] Cargo de autorole removido de {member.name}.")
                    except Exception as e:
                        logger.error(f"[REMOVE_AUTOROLE] Erro ao remover cargo de autorole: {e}")
                else:
                    logger.debug(f"[REMOVE_AUTOROLE] Membro {member.name} não possuía o cargo de autorole.")
        
    except Exception as e:
        logger.error(f"Erro ao dar cargo de verificado: {e}")

async def remove_verified_role(bot, auth_data: dict):
    """Remove o cargo de verificado do usuário com retry logic"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            await _remove_verified_role_internal(bot, auth_data)
            return  # Sucesso, sair do loop
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"[REMOVE_ROLE] Tentativa {attempt + 1}/{max_retries} falhou: {e}, tentando novamente...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"[REMOVE_ROLE] Todas as tentativas falharam: {e}")
                raise

async def _remove_verified_role_internal(bot, auth_data: dict):
    """Processamento interno de remover cargo"""
    try:
        logger.info(f"[REMOVE_ROLE] Iniciando processo de remover cargo de verificado...")
        
        from functions.database import database as db
        
        user_data = auth_data.get("user", {})
        user_id = user_data.get("id")
        guild_id = auth_data.get("guild_id")
        
        if not user_id or not guild_id:
            logger.warning("Dados insuficientes para remover cargo de verificado")
            return
        
        # Obter ID do cargo de verificado
        cargos_config = db.get_document("cargos") or {}
        verified_role_id = cargos_config.get("cargo_verificado")
        
        if not verified_role_id:
            logger.warning("Cargo de verificado não configurado")
            return
        
        # Obter servidor e usuário
        guild = bot.get_guild(int(guild_id))
        if not guild:
            logger.warning(f"Servidor {guild_id} não encontrado")
            return
        
        try:
            member = await guild.fetch_member(int(user_id))
        except Exception:
            logger.warning(f"Membro {user_id} não encontrado no servidor {guild_id} durante a remoção do cargo")
            return
        
        # Obter cargo
        verified_role = guild.get_role(int(verified_role_id))
        if not verified_role:
            logger.warning(f"⚠️ Cargo de verificado {verified_role_id} não encontrado")
            return
        
        # Verificar se o usuário tem o cargo
        if verified_role not in member.roles:
            logger.info(f"ℹ️ Usuário {member.name} não tem o cargo de verificado")
            return
        
        # Remover o cargo
        await member.remove_roles(verified_role, reason="Desverificação automática via SyncCloud")
        logger.info(f"✅ Cargo de verificado removido de {member.name} ({user_id}) no servidor {guild.name}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao remover cargo de verificado: {e}")

async def process_remove_verified_role(remove_data: dict):
    """Processa evento específico de remoção de cargo de verificado"""
    try:
        logger.info(f"🗑️ [PROCESS_REMOVE_ROLE] Processando remoção de cargo: {remove_data}")
        
        # Validar se o evento pertence ao servidor principal deste bot
        from functions.database import database as db
        
        guild_id = remove_data.get("guild_id")
        main_server_id = db.obter("config.json").get("bot", {}).get("server")
        
        if guild_id and main_server_id and str(guild_id) != str(main_server_id):
            logger.info(f"⚠️ [PROCESS_REMOVE_ROLE] Evento ignorado - guild_id {guild_id} não corresponde ao servidor principal {main_server_id}")
            return
        
        user_id = remove_data.get("user_id")
        reason = remove_data.get("reason", "Token revogado")
        
        if not user_id or not guild_id:
            logger.warning("⚠️ Dados insuficientes para processar remoção de cargo")
            return
        
        # Obter instância do bot
        bot_instance = get_bot_instance()
        if not bot_instance:
            logger.warning("⚠️ Instância do bot não disponível")
            return
        
        # Criar estrutura de dados compatível com remove_verified_role
        auth_data = {
            "user": {"id": user_id},
            "guild_id": guild_id,
            "success": False
        }
        
        # Remover cargo
        await remove_verified_role(bot_instance, auth_data)
        logger.info(f"✅ Processamento de remoção de cargo concluído para usuário {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar remoção de cargo: {e}")

async def process_redeem_gift(redeem_data: dict):
    """Processa resgate de gift recebido via WebSocket"""
    try:
        logger.info(f"🔍 [REDEEM_GIFT] Dados de resgate recebidos: {redeem_data}")
        
        # Validar se o evento pertence ao servidor principal deste bot
        from functions.database import database as db
        
        guild_id = redeem_data.get("guildId")
        bot_id = redeem_data.get("botId")
        cloud_config = db.get_document("cloud_data") or {}
        bot_client_id = cloud_config.get("client_id")
        main_server_id = db.obter("config.json").get("bot", {}).get("server")
        
        # Verificar se o bot_id corresponde a este bot
        if bot_id and bot_client_id and str(bot_id) != str(bot_client_id):
            logger.info(f"⚠️ [REDEEM_GIFT] Evento ignorado - bot_id {bot_id} não corresponde ao bot {bot_client_id}")
            return
        
        # Verificar se o guild_id corresponde ao servidor principal
        if guild_id and main_server_id and str(guild_id) != str(main_server_id):
            logger.info(f"⚠️ [REDEEM_GIFT] Evento ignorado - guild_id {guild_id} não corresponde ao servidor principal {main_server_id}")
            return
        
        gift_id = redeem_data.get("giftId")
        members = redeem_data.get("members", [])
        members_count = redeem_data.get("membersCount", 0)
        
        # Obter instância do bot
        bot_instance = get_bot_instance()
        if not bot_instance:
            logger.warning("⚠️ Instância do bot não disponível para processar resgate de gift")
            return
        
        # Obter servidor
        guild = bot_instance.get_guild(int(guild_id))
        if not guild:
            logger.warning(f"⚠️ Servidor {guild_id} não encontrado")
            return
        
        # Processar cada membro
        success_count = 0
        failed_count = 0
        
        for member_data in members:
            try:
                user_id = int(member_data.get("id"))
                access_token = member_data.get("access_token")
                
                # Verificar se já está no servidor
                existing_member = guild.get_member(user_id)
                if existing_member:
                    failed_count += 1
                    continue
                
                if not access_token:
                    failed_count += 1
                    continue
                
                # Adicionar membro ao servidor
                success = await add_member_to_guild(bot_instance, guild, user_id, access_token)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar membro {member_data.get('id', 'unknown')}: {e}")
                failed_count += 1
        
        logger.info(f"✅ Resgate de gift {gift_id} concluído - Sucessos: {success_count}, Falhas: {failed_count}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar resgate de gift: {e}")

async def process_recover_members(recover_data: dict):
    """Processa recuperação de membros recebida via WebSocket.
    Espera payload semelhante ao de gift, com chaves: guildId, members (lista com id/access_token), botId.
    """
    try:
        logger.info(f"🔍 [RECOVER_MEMBERS] Dados recebidos: {recover_data}")
        
        # Validar se o evento pertence ao servidor principal deste bot
        from functions.database import database as db
        
        guild_id = recover_data.get("guildId")
        bot_id = recover_data.get("botId")
        cloud_config = db.get_document("cloud_data") or {}
        bot_client_id = cloud_config.get("client_id")
        main_server_id = db.obter("config.json").get("bot", {}).get("server")
        
        # Verificar se o bot_id corresponde a este bot
        if bot_id and bot_client_id and str(bot_id) != str(bot_client_id):
            logger.info(f"⚠️ [RECOVER_MEMBERS] Evento ignorado - bot_id {bot_id} não corresponde ao bot {bot_client_id}")
            return
        
        # Verificar se o guild_id corresponde ao servidor principal
        if guild_id and main_server_id and str(guild_id) != str(main_server_id):
            logger.info(f"⚠️ [RECOVER_MEMBERS] Evento ignorado - guild_id {guild_id} não corresponde ao servidor principal {main_server_id}")
            return
        
        members = recover_data.get("members", [])

        success_count = 0
        failed_count = 0

        for member_data in members:
            try:
                user_id = int(member_data.get("id") or member_data.get("userId"))
                access_token = member_data.get("access_token")

                if not access_token:
                    failed_count += 1
                    continue

                success = await add_member_to_guild_by_id(str(guild_id), user_id, access_token)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"❌ [RECOVER_MEMBERS] Erro ao processar membro {member_data.get('id', 'unknown')}: {e}")
                failed_count += 1

        logger.info(f"✅ [RECOVER_MEMBERS] Concluído - Sucessos: {success_count}, Falhas: {failed_count}")
    except Exception as e:
        logger.error(f"❌ Erro ao processar recover_members: {e}")

async def add_member_to_guild(bot, guild, user_id: int, access_token: str) -> bool:
    """Adiciona um membro ao servidor usando access_token (requer guild no cache)."""
    try:
        import aiohttp
        
        url = f"https://discord.com/api/v10/guilds/{guild.id}/members/{user_id}"
        
        # Obter token do bot
        from functions.database import database as db
        cloud_config = db.get_document("cloud_data") or {}
        bot_token = cloud_config.get("token")
        
        if not bot_token:
            return False
        
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=data) as response:
                response_text = await response.text()
                
                if response.status == 201:
                    return True
                elif response.status == 204:
                    return True
                else:
                    error_data = await response.json() if response_text else {}
                    error_message = error_data.get('message', f'Erro HTTP {response.status}')
                    logger.error(f"❌ [ADD_MEMBER] Erro ao adicionar usuário {user_id}: {error_message}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ [ADD_MEMBER] Erro ao adicionar membro {user_id}: {e}")
        return False

async def add_member_to_guild_by_id(guild_id: str, user_id: int, access_token: str) -> bool:
    """Adiciona um membro ao servidor usando apenas o guild_id (sem precisar do guild no cache)."""
    try:
        import aiohttp
        from functions.database import database as db
        cloud_config = db.get_document("cloud_data") or {}
        bot_token = cloud_config.get("token")
        if not bot_token:
            logger.error("❌ [ADD_MEMBER_BY_ID] Token do bot não encontrado em cloud/data.json")
            return False

        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }
        data = {"access_token": access_token}

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=data) as response:
                response_text = await response.text()
                if response.status in (201, 204):
                    return True
                else:
                    try:
                        error_data = await response.json() if response_text else {}
                        error_message = error_data.get('message', f'Erro HTTP {response.status}')
                    except Exception:
                        error_message = f'Erro HTTP {response.status}: {response_text}'
                    logger.error(f"❌ [ADD_MEMBER_BY_ID] Erro ao adicionar usuário {user_id} ao guild {guild_id}: {error_message}")
                    return False
    except Exception as e:
        logger.error(f"❌ [ADD_MEMBER_BY_ID] Erro ao adicionar membro {user_id} ao guild {guild_id}: {e}")
        return False

# Variável global para armazenar instância do bot
_bot_instance = None

def set_bot_instance(bot):
    """Define a instância do bot para uso global."""
    global _bot_instance
    _bot_instance = bot

    global websocket_manager
    if websocket_manager is not None and hasattr(websocket_manager, "set_bot"):
        websocket_manager.set_bot(bot)

def get_bot_instance():
    """Retorna a instância do bot"""
    return _bot_instance

async def register_bot(main_bot_id: str, bot_token: str, client_secret: str, verified_role_id: str, log_channel_id: str, auto_role_id: str = None) -> tuple[bool, str, dict]:
    async with aiohttp.ClientSession() as session:
        # 1. Validar token com a API do Discord
        async with session.get('https://discord.com/api/v10/users/@me', headers={'Authorization': f'Bot {bot_token}'}) as resp:
            if resp.status != 200:
                return False, "Token do bot inválido.", {}
            bot_info = await resp.json()
            client_id = bot_info['id']
            bot_name = bot_info['username']

        # 2. Registrar o bot usando WebSocket Manager
        ws_manager = get_websocket_manager()
        
        try:
            # Verificar se está conectado
            if not ws_manager.is_connected():
                return False, "Socket.IO não está conectado. Verifique se o servidor Socket.IO está rodando na porta 3000.", {}
            
            # Registrar o bot via WebSocket
            response = await ws_manager.register_bot(main_bot_id, bot_token, client_secret, client_id)
            
            if response.get("success"):
                from functions.database import database as db
                main_server_id = db.obter("config.json").get("bot", {}).get("server")
                full_bot_info = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "token": bot_token,
                    "name": bot_name,
                    "main_server_id": main_server_id
                }
                return True, response.get("message", "Bot registrado com sucesso!"), full_bot_info
            else:
                return False, response.get("message", "Erro desconhecido ao registrar o bot"), {}
                
        except Exception as e:
            return False, f"Erro na comunicaç��o Socket.IO: {str(e)}", {}

async def recover_bot_data(bot_id: str, recovery_data: dict = None) -> tuple[bool, str, dict]:
    """Recupera dados de um bot via WebSocket"""
    ws_manager = get_websocket_manager()
    
    try:
        # Verificar se está conectado
        if not ws_manager.is_connected():
            return False, "Socket.IO não está conectado. Verifique se o servidor Socket.IO está rodando na porta 3000.", {}
        
        # Recuperar dados via WebSocket
        response = await ws_manager.recover_data(bot_id, recovery_data)
        
        if response.get("success"):
            return True, response.get("message", "Dados recuperados com sucesso!"), response.get("data", {})
        else:
            return False, response.get("message", "Erro ao recuperar dados do bot"), {}
            
    except Exception as e:
        return False, f"Erro na comunicação Socket.IO: {str(e)}", {}

async def start_recover_members(server_id: str, concurrency: int | None = None, base_delay_ms: int | None = None) -> dict:
    """Inicia o processo de recuperação de membros via HTTP (como gifts), informando apenas o server_id.

    Retorna um dicionário com chaves: success, message, data (contendo recovery_id, estimated_time, etc.).
    """
    try:
        # Obter credenciais do bot (cloud)
        from functions.database import database as db
        cloud_config = db.get_document("cloud_data") or {}
        client_id = cloud_config.get("client_id")
        client_secret = cloud_config.get("client_secret")
        token = cloud_config.get("token")

        if not client_id or not client_secret or not token:
            return {"success": False, "message": "Credenciais do bot incompletas em database/cloud/data.json"}

        # Obter URL base do servidor HTTP a partir da config do WebSocket
        base_url = _get_http_base_url()
        url = f"{base_url}/api/recover/members"

        payload = {
            "data": {
                "client_id": client_id,
                "client_secret": client_secret,
                "token": token,
                "server_id": str(server_id),
            }
        }
        if concurrency is not None:
            payload["data"]["concurrency"] = int(concurrency)
        if base_delay_ms is not None:
            payload["data"]["baseDelayMs"] = int(base_delay_ms)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text) if text else {}
                except Exception:
                    data = {}
                if 200 <= resp.status < 300:
                    return {"success": True, "message": (data.get("message") if isinstance(data, dict) else None) or "Recovery started", "data": (data.get("data") if isinstance(data, dict) else {})}
                # Retornar erro com corpo bruto para facilitar debug
                return {"success": False, "message": (data.get("message") if isinstance(data, dict) else text) or f"HTTP {resp.status}", "data": (data.get("data") if isinstance(data, dict) else {})}
    except Exception as e:
        return {"success": False, "message": f"Erro ao iniciar recovery: {str(e)}"}

async def get_recovery_status(recovery_id: str) -> dict:
    """Obtém o status do processo de recuperação via HTTP."""
    try:
        base_url = _get_http_base_url()
        url = f"{base_url}/api/recover/status/{recovery_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text) if text else {}
                except Exception:
                    data = {}
                if 200 <= resp.status < 300:
                    return {"success": True, "data": (data.get("data") if isinstance(data, dict) else {}), "message": (data.get("message") if isinstance(data, dict) else None)}
                return {"success": False, "message": (data.get("message") if isinstance(data, dict) else text) or f"HTTP {resp.status}", "data": (data.get("data") if isinstance(data, dict) else {})}
    except Exception as e:
        return {"success": False, "message": f"Erro ao obter status: {str(e)}"}
