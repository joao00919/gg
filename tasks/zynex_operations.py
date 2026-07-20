from __future__ import annotations

import calendar
from datetime import datetime
import logging
import os

import disnake
from disnake.ext import commands, tasks

from functions.alerts import record_alert
from functions.database import database as db
from functions.database_backup import create_database_backup
from modules.loja.cart.purchase_manager import PurchaseManager

logger = logging.getLogger("zynex.operations")


def _enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "sim", "on"}


class ZYNEXOperations(commands.Cog):
    """Backups rotativos e relatório mensal; não realiza operações financeiras."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._loops_started = False

    @commands.Cog.listener("on_ready")
    async def start_background_loops(self):
        """Inicia os loops somente quando o event loop do Discord já está ativo."""
        if self._loops_started:
            return
        self._loops_started = True
        if not self.daily_backup.is_running():
            self.daily_backup.start()
        if not self.monthly_report.is_running():
            self.monthly_report.start()
        logger.info("Rotinas de backup e relatório mensal iniciadas.")

    def cog_unload(self):
        self.daily_backup.cancel()
        self.monthly_report.cancel()

    @tasks.loop(hours=24)
    async def daily_backup(self):
        if not _enabled("ZYNEX_AUTOMATIC_BACKUP", True):
            return
        try:
            result = create_database_backup(reason="automatic")
            db.save_document("zynex_backup_metadata", {"last_backup": result})
            logger.info("Backup automático concluído: %s", result.get("path"))
        except Exception as exc:
            logger.exception("Falha no backup automático")
            record_alert("backup_failure", "Falha no backup automático.", details={"error": str(exc)[:300]})

    @daily_backup.before_loop
    async def before_daily_backup(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=6)
    async def monthly_report(self):
        if not _enabled("ZYNEX_MONTHLY_REPORT", True):
            return
        now = datetime.now().astimezone()
        last_day = calendar.monthrange(now.year, now.month)[1]
        if now.day != last_day:
            return
        competence = f"{now.year:04d}-{now.month:02d}"
        registry = db.get_document("zynex_monthly_reports") or {"competencies": {}}
        if competence in registry.setdefault("competencies", {}):
            return
        owner_id = os.getenv("OWNER_ID") or ((db.get_document("config") or {}).get("bot") or {}).get("owner")
        if not owner_id:
            logger.warning("Relatório mensal não enviado: OWNER_ID não configurado.")
            return
        stats = PurchaseManager.get_statistics()
        products = list((stats.get("products_sold") or {}).values())
        products.sort(key=lambda item: float(item.get("revenue", 0) or 0), reverse=True)
        top = products[0] if products else {}
        content = (
            "📊 **Estatísticas da conta**\n\n"
            f"Total vendido: **R$ {float(stats.get('total_revenue', 0) or 0):.2f}**\n"
            f"Quantidade de vendas: **{stats.get('total_purchases', 0)}**\n"
            f"Produtos vendidos: **{stats.get('total_items_sold', 0)}**\n"
            f"Produto mais vendido: **{top.get('name', 'Nenhum')}**\n"
            f"Clientes únicos: **{stats.get('unique_customers', 0)}**\n"
            f"Ticket médio: **R$ {float(stats.get('average_ticket', 0) or 0):.2f}**\n\n"
            "-# Dados internos. A API de pagamento permanece inalterada."
        )
        try:
            user = self.bot.get_user(int(owner_id)) or await self.bot.fetch_user(int(owner_id))
            await user.send(content, allowed_mentions=disnake.AllowedMentions.none())
            registry["competencies"][competence] = {"sentAt": now.isoformat(), "ownerId": str(owner_id)}
            db.save_document("zynex_monthly_reports", registry)
        except Exception as exc:
            logger.exception("Falha ao enviar relatório mensal")
            record_alert("internal_error", "Falha ao enviar relatório mensal.", details={"error": str(exc)[:300], "competence": competence})

    @monthly_report.before_loop
    async def before_monthly_report(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(ZYNEXOperations(bot))
