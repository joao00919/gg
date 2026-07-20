from __future__ import annotations

import asyncio

from disnake.ext import tasks

import core

_bot_instance = None


@tasks.loop(hours=6)
async def change_bio_task(bot):
    global _bot_instance
    _bot_instance = bot
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, core.change_bio)
    except Exception as exc:
        print(f"[Perfil] Falha na atualização programada: {exc}")


@change_bio_task.before_loop
async def before_change_bio_task():
    if _bot_instance:
        await _bot_instance.wait_until_ready()
