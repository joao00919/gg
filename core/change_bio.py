"""Atualização opcional da descrição da aplicação Discord."""

from __future__ import annotations

import os

import requests


def change_bio(token: str | None = None, application_id: str | None = None) -> bool:
    description = os.getenv("APPLICATION_DESCRIPTION", "").strip()
    if not description:
        return False

    token = (token or os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
    application_id = (application_id or os.getenv("DISCORD_CLIENT_ID") or "").strip()
    if not token or not application_id:
        raise RuntimeError("DISCORD_TOKEN/BOT_TOKEN e DISCORD_CLIENT_ID são necessários para atualizar a descrição.")

    response = requests.patch(
        f"https://discord.com/api/v10/applications/{application_id}",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        },
        json={"description": description[:400]},
        timeout=15,
    )
    if response.status_code not in {200, 204}:
        raise RuntimeError(f"Discord recusou a atualização da descrição: HTTP {response.status_code}")
    return True
