from __future__ import annotations

import time

import disnake
from disnake.ext import commands, tasks

from functions.automation_rules import escalate_priority, is_ticket_stale, merge_rules, stock_is_low
from functions.database import database as db
from functions.emoji import emoji
from functions.permission_matrix import get_config as get_permission_config
from modules.loja.cart.stock_manager import StockManager


class BusinessRulesTask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rule_loop.start()

    def cog_unload(self):
        self.rule_loop.cancel()

    @tasks.loop(minutes=5)
    async def rule_loop(self):
        rules = merge_rules(db.get_document("automation_rules") or {})
        if not rules.get("enabled", True):
            return
        await self._check_low_stock(rules["stock"])
        await self._check_stale_tickets(rules["tickets"])

    @rule_loop.before_loop
    async def before_rule_loop(self):
        await self.bot.wait_until_ready()

    async def _notify_admin(self, text: str, channel_id=None):
        if channel_id:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                try:
                    await channel.send(text)
                    return
                except Exception:
                    pass
        for guild in self.bot.guilds:
            owner = guild.owner
            if owner:
                try:
                    await owner.send(text)
                except Exception:
                    pass

    async def _check_low_stock(self, settings: dict):
        if not settings.get("enabled", True):
            return
        products = db.get_document("loja_products") or {}
        changed = False
        notifications = db.get_document("automation_notifications") or {"stock": {}}
        stock_state = notifications.setdefault("stock", {})

        for product_id, product in products.items():
            fields = product.get("campos") or {}
            if not fields:
                continue
            threshold = int((product.get("automation") or {}).get("low_stock_threshold") or settings.get("threshold", 5))
            quantities = []
            for field_id, field in fields.items():
                if (field.get("infinite_stock") or {}).get("enabled"):
                    continue
                quantities.append(StockManager.get_available_stock(product_id, field_id))
            if not quantities:
                continue
            quantity = sum(quantities)
            low = stock_is_low(quantity, threshold)
            info = product.setdefault("info", {})
            previous = bool(info.get("low_stock"))
            if settings.get("mark_low_stock", True):
                info["low_stock"] = low
            if low and settings.get("disable_promotion", True):
                promotion = product.setdefault("promotion", {})
                if promotion.get("enabled"):
                    promotion["enabled"] = False
                    promotion["disabled_by_low_stock"] = True
            if previous != low:
                changed = True
            key = str(product_id)
            if low and not stock_state.get(key):
                stock_state[key] = {"notified_at": int(time.time()), "quantity": quantity}
                if settings.get("notify_admin", True):
                    await self._notify_admin(
                        f"{emoji.cardbox} **Estoque baixo**\n"
                        f"Produto: **{product.get('name', product_id)}**\n"
                        f"Disponível: `{quantity}` | Limite: `{threshold}`",
                        settings.get("channel_id"),
                    )
            elif not low and stock_state.pop(key, None):
                changed = True

        if changed:
            db.save_document("loja_products", products)
        db.save_document("automation_notifications", notifications)

    async def _check_stale_tickets(self, settings: dict):
        if not settings.get("enabled", True):
            return
        data = db.get_document("tickets_data") or {}
        config = db.get_document("tickets_config") or {}
        now = int(time.time())
        changed = False
        support_role_id = (get_permission_config().get("role_ids") or {}).get("support")

        for panel_id, users in (data.get("panels") or {}).items():
            panel_cfg = (config.get("panels") or {}).get(panel_id, {})
            panel_rules = {**settings, **(panel_cfg.get("automation") or {})}
            for _owner_id, ticket_list in (users or {}).items():
                for ticket in ticket_list or []:
                    if not is_ticket_stale(ticket, now, panel_rules.get("stale_minutes", 30)):
                        continue
                    last_alert = int(ticket.get("stale_alerted_at") or 0)
                    if last_alert and now - last_alert < int(panel_rules.get("stale_minutes", 30)) * 60:
                        continue
                    channel = self.bot.get_channel(int(ticket.get("ticket_id") or 0))
                    if not channel:
                        continue
                    if panel_rules.get("raise_priority", True):
                        ticket["priority"] = escalate_priority(ticket.get("priority"))
                    ticket["stale_alerted_at"] = now
                    changed = True
                    mention = f"<@&{support_role_id}> " if support_role_id and panel_rules.get("mention_support", True) else ""
                    try:
                        await channel.send(
                            f"{mention}{emoji.interrogation} **Alerta de atendimento parado**\n"
                            f"Este ticket está sem resposta há pelo menos "
                            f"**{panel_rules.get('stale_minutes', 30)} minutos**.\n"
                            f"Prioridade atual: **{str(ticket.get('priority', 'normal')).upper()}**",
                            allowed_mentions=disnake.AllowedMentions(roles=True),
                        )
                    except Exception:
                        pass
        if changed:
            db.save_document("tickets_data", data)


def setup(bot: commands.Bot):
    bot.add_cog(BusinessRulesTask(bot))
