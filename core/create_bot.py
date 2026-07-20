from __future__ import annotations

import base64
import logging
import os

import disnake
import requests
from disnake.ext import commands
from dotenv import load_dotenv

from functions.database import database as db

load_dotenv()
logger = logging.getLogger(__name__)
DISCORD_API = "https://discord.com/api/v10"


def resolve_discord_token(*fallbacks: str) -> str:
    """Resolve BOT_TOKEN/DISCORD_TOKEN sem persistir a credencial em arquivos."""
    token = (
        os.getenv("DISCORD_TOKEN")
        or os.getenv("BOT_TOKEN")
        or next((value for value in fallbacks if value), "")
        or ""
    ).strip()
    if token.lower().startswith("bot "):
        token = token[4:].strip()
    return token


def _decode_client_id_from_token(token: str) -> str:
    """Extrai o ID da aplicação do primeiro segmento do token do Discord."""
    if not token or "." not in token:
        return ""
    try:
        first_segment = token.split(".", 1)[0]
        padded = first_segment + ("=" * (-len(first_segment) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8").strip()
        return decoded if decoded.isdigit() else ""
    except Exception:
        return ""


def _fetch_client_id_from_discord(token: str) -> str:
    """Consulta o Discord somente se o formato do token não permitir a extração local."""
    if not token:
        return ""
    try:
        response = requests.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bot {token}"},
            timeout=12,
        )
        response.raise_for_status()
        value = str((response.json() or {}).get("id") or "").strip()
        return value if value.isdigit() else ""
    except Exception:
        return ""


def resolve_discord_client_id(token: str, *fallbacks: str) -> str:
    """Resolve o ID da aplicação usando o token como fonte de verdade.

    Um DISCORD_CLIENT_ID pertencente a outra aplicação faz os emojis serem
    sincronizados no lugar errado e o Discord rejeita todos os painéis. Por isso,
    quando o token permite identificar o ID, ele sempre prevalece.
    """
    explicit = (
        os.getenv("DISCORD_CLIENT_ID")
        or next((value for value in fallbacks if value), "")
        or ""
    ).strip()
    if explicit and not explicit.isdigit():
        raise RuntimeError("DISCORD_CLIENT_ID deve conter apenas números.")

    derived = _decode_client_id_from_token(token) or _fetch_client_id_from_discord(token)
    if derived:
        if explicit and explicit != derived:
            logger.warning(
                "DISCORD_CLIENT_ID=%s não pertence ao token atual; usando automaticamente %s.",
                explicit,
                derived,
            )
        os.environ["DISCORD_CLIENT_ID"] = derived
        logger.info("Aplicação Discord confirmada pelo token: %s.", derived)
        return derived

    if explicit:
        logger.warning(
            "Não foi possível validar o ID pelo token; usando DISCORD_CLIENT_ID=%s.",
            explicit,
        )
        return explicit

    raise RuntimeError(
        "Não foi possível identificar o DISCORD_CLIENT_ID pelo token. "
        "Confirme se BOT_TOKEN/DISCORD_TOKEN é um token de bot válido."
    )


def obter_info():
    data = db.obter("config.json")
    token = resolve_discord_token(data.get("botToken", ""))
    api_url = data.get("apiURL", "").rstrip("/")
    if not token:
        raise RuntimeError("Configure DISCORD_TOKEN ou BOT_TOKEN.")
    bot_id = resolve_discord_client_id(token, data.get("botID", ""))
    if not api_url:
        raise RuntimeError("Para saveConfig=true, configure apiURL no config.json.")
    response = requests.get(
        f"{api_url}/api/bot/{bot_id}/info",
        headers={"authorization": token, "content-type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def salvar_info(info: dict):
    config_db = db.obter("config.json")
    config_db["bot"] = {key: info.get(key, "") for key in ("owner", "id", "perms", "server")}
    # Tokens nunca são persistidos em arquivos locais.
    config_db["bot"]["token"] = ""
    if "version" in info:
        config_db["version"] = info["version"]
    db.salvar("config.json", config_db)


def _parse_optional_id(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    if not value.isdigit():
        raise RuntimeError(f"{name} deve conter apenas números.")
    return int(value)


def create_bot() -> tuple[commands.Bot, str, str]:
    config_db = db.obter("config.json")
    if config_db.get("saveConfig") is True:
        info = obter_info()
        salvar_info(info)
    else:
        info = config_db.get("bot", {})

    token = resolve_discord_token(config_db.get("botToken"), info.get("token"))
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN/BOT_TOKEN não foi configurado. "
            "Informe o token nas variáveis da hospedagem."
        )

    application_id = resolve_discord_client_id(
        token,
        info.get("id"),
        config_db.get("botID"),
    )

    intents = disnake.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    test_guild_id = _parse_optional_id("DISCORD_TEST_GUILD_ID")
    bot_kwargs = {
        "command_prefix": commands.when_mentioned,
        "intents": intents,
        "help_command": None,
        "reload": True,
    }
    if test_guild_id:
        bot_kwargs["test_guilds"] = [test_guild_id]
        logger.info("Comandos em modo de teste no servidor %s.", test_guild_id)

    bot = commands.Bot(**bot_kwargs)
    return bot, token, application_id
