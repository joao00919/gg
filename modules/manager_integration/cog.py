import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Deque

import disnake
from aiohttp import web
from disnake.ext import commands

from connections.mongo_db import get_storage_info
from functions.database import database as db


class RingLogHandler(logging.Handler):
    def __init__(self, storage: Deque[str]):
        super().__init__()
        self.storage = storage

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.storage.append(self.format(record))
        except Exception:
            pass


class ManagerIntegration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self.suspended = False
        self.logs: Deque[str] = deque(maxlen=500)
        handler = RingLogHandler(self.logs)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        self.log_handler = handler

    def cog_unload(self):
        logging.getLogger().removeHandler(self.log_handler)
        if self.runner:
            asyncio.create_task(self.runner.cleanup())

    @commands.Cog.listener()
    async def on_ready(self):
        if os.getenv("PRIVATE_API_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "sim", "on"}:
            logging.getLogger(__name__).info("API privada desativada por PRIVATE_API_ENABLED=false.")
            return
        if self.runner is not None:
            return
        app = web.Application(middlewares=[self._auth_middleware])
        app.router.add_get("/health", self.health)
        app.router.add_post("/webhooks/purincash", self.purincash_webhook)
        app.router.add_get("/internal/v1/applications/{application_id}/status", self.status)
        app.router.add_post("/internal/v1/applications/{application_id}/restart", self.restart)
        app.router.add_post("/internal/v1/applications/{application_id}/suspend", self.suspend)
        app.router.add_post("/internal/v1/applications/{application_id}/activate", self.activate)
        app.router.add_get("/internal/v1/applications/{application_id}/logs", self.get_logs)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        port = int(os.getenv("PRIVATE_API_PORT", os.getenv("PORT", "8080")))
        self.site = web.TCPSite(self.runner, "0.0.0.0", port)
        try:
            await self.site.start()
        except OSError as exc:
            await self.runner.cleanup()
            self.runner = None
            self.site = None
            raise RuntimeError(f"Não foi possível abrir a porta {port}: {exc}") from exc
        logging.getLogger(__name__).info("API privada ativa em 0.0.0.0:%s", port)

    def _expected_application_id(self) -> str:
        return os.getenv("MANAGER_APPLICATION_ID", "").strip()

    def _check_application(self, request: web.Request) -> None:
        expected = self._expected_application_id()
        received = request.match_info.get("application_id", "")
        if expected and received != expected:
            raise web.HTTPNotFound(text=json.dumps({"message": "Aplicação não encontrada."}), content_type="application/json")

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        if request.path in {"/health", "/webhooks/purincash"}:
            return await handler(request)
        secret = os.getenv("SALES_BOT_API_KEY", "").strip()
        if len(secret) < 32:
            raise web.HTTPServiceUnavailable(text=json.dumps({"message": "SALES_BOT_API_KEY não configurada."}), content_type="application/json")
        api_key = request.headers.get("x-api-key", "")
        timestamp = request.headers.get("x-timestamp", "")
        signature = request.headers.get("x-signature", "")
        if not hmac.compare_digest(api_key, secret):
            raise web.HTTPUnauthorized(text=json.dumps({"message": "Não autorizado."}), content_type="application/json")
        try:
            ts = int(timestamp)
        except ValueError:
            raise web.HTTPUnauthorized(text=json.dumps({"message": "Timestamp inválido."}), content_type="application/json")
        if abs(int(time.time() * 1000) - ts) > 300_000:
            raise web.HTTPUnauthorized(text=json.dumps({"message": "Requisição expirada."}), content_type="application/json")
        raw_body = await request.text()
        material = f"{timestamp}.{request.method.upper()}.{request.path_qs}.{raw_body}".encode("utf-8")
        expected_sig = base64.urlsafe_b64encode(hmac.new(secret.encode("utf-8"), material, hashlib.sha256).digest()).rstrip(b"=").decode("ascii")
        if not hmac.compare_digest(signature, expected_sig):
            raise web.HTTPUnauthorized(text=json.dumps({"message": "Assinatura inválida."}), content_type="application/json")
        request["raw_body"] = raw_body
        return await handler(request)

    @staticmethod
    def _contains_payment_id(value, payment_id: str) -> bool:
        if isinstance(value, dict):
            return any(ManagerIntegration._contains_payment_id(item, payment_id) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(ManagerIntegration._contains_payment_id(item, payment_id) for item in value)
        return str(value) == payment_id

    async def _process_purincash_event(self, payload: dict, webhook_id: str) -> None:
        event = str(payload.get("event") or "")
        if event not in {"payment.paid", "charge.paid"}:
            return
        payment_id = str(payload.get("paymentId") or "").strip()
        if not payment_id:
            return

        cart_id = None
        metadata = payload.get("metadata")
        if isinstance(metadata, str) and metadata.strip():
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        if isinstance(metadata, dict):
            cart_id = metadata.get("cartId") or metadata.get("cart_id")

        loja_data = db.get_document("loja_data") or {}
        carts = loja_data.get("carts") or {}
        if not cart_id:
            for candidate_id, cart in carts.items():
                if self._contains_payment_id((cart or {}).get("payment_data", {}), payment_id):
                    cart_id = candidate_id
                    break
        if not cart_id or cart_id not in carts:
            logging.getLogger(__name__).warning(
                "Webhook PurinCash %s recebido, mas nenhum carrinho foi encontrado para %s.",
                webhook_id,
                payment_id,
            )
            return

        from modules.loja.cart.checkout import _handle_payment_approved
        await _handle_payment_approved(str(cart_id), self.bot)

    async def purincash_webhook(self, request: web.Request):
        raw = await request.read()
        signature = (request.headers.get("X-Webhook-Signature") or "").strip()
        webhook_id = (request.headers.get("X-Webhook-Id") or "").strip()
        secret = (os.getenv("PURINCASH_WEBHOOK_SECRET") or "").strip()
        if not secret:
            return web.json_response({"ok": False, "error": "Webhook secret not configured"}, status=503)
        expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            return web.json_response({"ok": False, "error": "Invalid signature"}, status=401)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

        if not webhook_id:
            webhook_id = f"{payload.get('event', 'event')}:{payload.get('paymentId') or payload.get('withdrawalId') or hashlib.sha256(raw).hexdigest()}"
        events = db.get_document("purincash_webhook_events") or {"items": {}}
        items = events.setdefault("items", {})
        if webhook_id in items:
            return web.json_response({"ok": True, "duplicate": True})
        items[webhook_id] = {
            "event": payload.get("event"),
            "received_at": int(time.time()),
            "status": "received",
        }
        # Evita crescimento ilimitado no banco local.
        if len(items) > 2000:
            ordered = sorted(items.items(), key=lambda pair: pair[1].get("received_at", 0), reverse=True)
            events["items"] = dict(ordered[:1500])
        db.save_document("purincash_webhook_events", events)
        asyncio.create_task(self._process_purincash_event(payload, webhook_id))
        return web.json_response({"ok": True})

    async def health(self, _request: web.Request):
        storage = get_storage_info()
        return web.json_response({
            "ok": True,
            "service": "zynex-sales-private-api",
            "version": "4.3.3",
            "ready": self.bot.is_ready(),
            "storage": storage.get("driver"),
        })

    async def status(self, request: web.Request):
        self._check_application(request)
        state = "SUSPENDED" if self.suspended else ("ONLINE" if self.bot.is_ready() else "OFFLINE")
        return web.json_response({
            "state": state,
            "version": "ZYNEX-Systems-4.3.3-PurinCash",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "latencyMs": round(self.bot.latency * 1000, 2),
        })

    async def restart(self, request: web.Request):
        self._check_application(request)
        async def exit_later():
            await asyncio.sleep(0.75)
            os._exit(0)
        asyncio.create_task(exit_later())
        return web.json_response({"accepted": True, "state": "ONLINE", "message": "Reinicialização enviada para a Shard."})

    async def suspend(self, request: web.Request):
        self._check_application(request)
        self.suspended = True
        await self.bot.change_presence(status=disnake.Status.dnd, activity=disnake.Game("Aplicação suspensa"))
        return web.json_response({"ok": True, "state": "SUSPENDED"})

    async def activate(self, request: web.Request):
        self._check_application(request)
        self.suspended = False
        await self.bot.change_presence(status=disnake.Status.online)
        return web.json_response({"ok": True, "state": "ONLINE"})

    async def get_logs(self, request: web.Request):
        self._check_application(request)
        try:
            limit = max(1, min(200, int(request.query.get("limit", "50"))))
        except ValueError:
            limit = 50
        return web.json_response({"logs": list(self.logs)[-limit:]})


def setup(bot: commands.Bot):
    bot.add_cog(ManagerIntegration(bot))
