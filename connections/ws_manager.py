"""
WebSocket Manager for ZYNEX Systems
Uses pure websockets library with uvloop for high performance
"""

import asyncio
import json
import logging
import traceback
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import uuid

# Não altera a política global de event loop durante importação. Fazer isso
# depois que o bot criou o loop remove o loop atual e quebra o disnake no Linux.
try:
    import uvloop  # noqa: F401
    _USING_UVLOOP = True
except ImportError:
    _USING_UVLOOP = False

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

logger = logging.getLogger(__name__)


class WSManager:
    """WebSocket Manager using pure websockets + asyncio + uvloop"""

    def __init__(self, bot):
        self.bot = bot
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.should_reconnect = True
        self.reconnect_interval = 5
        self.reconnect_attempts = 0

        self.server_url = None
        self.jwt_secret = None
        self.bot_id = None

        self.handlers: Dict[str, Callable] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}

        logger.info(f"WSManager initialized (uvloop: {_USING_UVLOOP})")

    # =====================================================
    # EVENT SYSTEM
    # =====================================================

    def on(self, event: str):
        """Decorator to register event handler"""
        def decorator(func):
            self.handlers[event] = func
            return func
        return decorator

    def _register_default_handlers(self):

        @self.on("connected")
        async def on_connected(data):
            return None

    # =====================================================
    # CONNECTION
    # =====================================================

    async def connect(self):
        try:
            token = self._generate_token()

            ws_url = self.server_url
            if not ws_url:
                logger.info("WebSocket externo não configurado; conexão ignorada.")
                self.should_reconnect = False
                return

            if ws_url.startswith("http://"):
                ws_url = "ws://" + ws_url[7:]
            elif ws_url.startswith("https://"):
                ws_url = "wss://" + ws_url[8:]
            elif not ws_url.startswith(("ws://", "wss://")):
                ws_url = "ws://" + ws_url

            uri = f"{ws_url}?token={token}"

            logger.info(f"Connecting to {ws_url}...")

            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=60,
                close_timeout=10,
                max_size=10_000_000,
            ) as ws:

                self.ws = ws
                self.connected = True
                self.reconnect_attempts = 0

                logger.info("WebSocket connected!")

                await self._send_bot_info()
                await self._listen()

        except ConnectionClosedError as e:
            logger.warning(f"Connection closed: {e}")

        except ConnectionClosedOK:
            logger.info("Connection closed normally")

        except Exception:
            traceback.print_exc()

        self.connected = False
        self.ws = None

        if self.should_reconnect:
            self.reconnect_attempts += 1
            wait_time = min(5 * (1.5 ** self.reconnect_attempts), 60)
            await asyncio.sleep(wait_time)
            asyncio.create_task(self.connect())

    async def disconnect(self):
        self.should_reconnect = False

        if self.ws:
            await self.ws.close()

        self.connected = False
        self.ws = None
        logger.info("Disconnected from WebSocket")

    def is_connected(self) -> bool:
        return self.connected and self.ws is not None

    # =====================================================
    # TOKEN
    # =====================================================

    def _generate_token(self) -> str:
        try:
            import jwt

            payload = {
                "botId": str(self.bot_id),
                "discordId": str(self.bot.user.id) if self.bot and self.bot.user else None,
                "exp": datetime.utcnow() + timedelta(hours=24),
                "iat": datetime.utcnow(),
            }

            if not self.jwt_secret:
                raise RuntimeError("JWT_SECRET não configurado para a conexão WebSocket.")
            return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

        except Exception as exc:
            raise RuntimeError(f"Falha ao gerar token WebSocket: {exc}") from exc

    # =====================================================
    # LISTENER
    # =====================================================

    async def _listen(self):
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    event = data.get("event")
                    payload = data.get("data", {})

                    if event in self.handlers:
                        asyncio.create_task(self.handlers[event](payload))

                except Exception:
                    pass

        except Exception:
            pass

    # =====================================================
    # SEND / REQUEST
    # =====================================================

    async def send(self, event: str, data: dict):
        if not self.ws or not self.connected:
            return False

        try:
            message = json.dumps({
                "event": event,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })

            await self.ws.send(message)
            return True

        except Exception:
            return False

    async def request(self, event: str, data: dict, timeout: float = 30.0):
        request_id = str(uuid.uuid4())

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_requests[request_id] = future

        success = await self.send(event, data)

        if not success:
            return {"success": False}

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return {"success": False, "message": "timeout"}

    async def _send_bot_info(self):
        if not self.bot or not self.bot.user:
            return

        guilds = [str(g.id) for g in self.bot.guilds] if self.bot.guilds else []

        data = {
            "bot_id": str(self.bot.user.id),
            "guilds": guilds
        }

        await self.send("bot_connected", data)
