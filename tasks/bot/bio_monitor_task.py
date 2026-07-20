"""Monitor opcional da descrição da aplicação.

Desativado por padrão. Não encerra o bot e não envia DMs em massa.
"""

from __future__ import annotations

import asyncio
import os

import requests
from disnake.ext import tasks

import core

_bot_instance = None


def get_expected_bio() -> str:
    return os.getenv("APPLICATION_DESCRIPTION", "").strip()


def get_current_bio(token: str, app_id: str) -> str:
    response = requests.get(
        f"https://discord.com/api/v10/applications/{app_id}",
        headers={"Authorization": f"Bot {token}"},
        timeout=10,
    )
    if response.status_code == 200:
        return response.json().get("description", "")
    return ""


@tasks.loop(minutes=15)
async def bio_monitor_task(bot):
    global _bot_instance
    _bot_instance = bot

    token = (os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
    app_id = os.getenv("DISCORD_CLIENT_ID", "").strip()
    expected = get_expected_bio()
    if not token or not app_id or not expected:
        return

    try:
        loop = asyncio.get_running_loop()
        current = await loop.run_in_executor(None, get_current_bio, token, app_id)
        if current.strip() != expected:
            await loop.run_in_executor(None, core.change_bio, token, app_id)
            print("[Perfil] Descrição restaurada conforme APPLICATION_DESCRIPTION.")
    except Exception as exc:
        print(f"[Perfil] Falha no monitoramento: {exc}")


@bio_monitor_task.before_loop
async def before_bio_monitor_task():
    if _bot_instance:
        await _bot_instance.wait_until_ready()
