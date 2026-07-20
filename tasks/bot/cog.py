from __future__ import annotations

import asyncio
import os

from disnake.ext import commands

import core
from .bio_monitor_task import bio_monitor_task
from .change_bio_task import change_bio_task
from .status_rotator import status_rotator_task


def _enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


class StatusRotatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._bio_updated_once = False

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        if not status_rotator_task.is_running():
            status_rotator_task.start(self.bot)

        # Alterações no perfil da aplicação são opt-in.
        if _enabled("AUTO_UPDATE_APPLICATION_PROFILE", False) and not self._bio_updated_once:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, core.change_bio)
                self._bio_updated_once = True
                print("[Perfil] Descrição da aplicação atualizada.")
            except Exception as exc:
                print(f"[Perfil] Não foi possível atualizar a descrição: {exc}")

        if _enabled("AUTO_UPDATE_APPLICATION_PROFILE", False) and not change_bio_task.is_running():
            change_bio_task.start(self.bot)

        if _enabled("MONITOR_APPLICATION_PROFILE", False) and not bio_monitor_task.is_running():
            bio_monitor_task.start(self.bot)


def setup(bot: commands.Bot):
    bot.add_cog(StatusRotatorCog(bot))
