"""Seleção do backend de persistência.

- STORAGE_DRIVER=local: usa JSON local, sem MongoDB.
- STORAGE_DRIVER=mongo: exige MONGO_URL.
- STORAGE_DRIVER=auto: usa MongoDB quando MONGO_URL existe; caso contrário, usa local.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .local_db import LocalCollection

load_dotenv()


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


config = _read_json("config.json")
mongo_config = _read_json("configs/config_mongo.json")

mongo_url = (os.getenv("MONGO_URL") or mongo_config.get("mongoURL") or "").strip()
database_name = (
    os.getenv("MONGO_DATABASE") or mongo_config.get("databaseName") or "zynex_sales"
).strip()
bot_id = (
    os.getenv("DISCORD_CLIENT_ID")
    or (config.get("bot") or {}).get("id")
    or config.get("botID")
    or "local"
)

driver = os.getenv("STORAGE_DRIVER", "auto").strip().lower()
if driver not in {"auto", "local", "mongo"}:
    raise RuntimeError("STORAGE_DRIVER deve ser 'auto', 'local' ou 'mongo'.")
if driver == "auto":
    driver = "mongo" if mongo_url else "local"

client = None
database = None

if driver == "local":
    local_path = os.getenv("LOCAL_DATABASE_PATH", "data/local_database.json").strip()
    if not local_path:
        local_path = "data/local_database.json"
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    collection = LocalCollection(local_path)
    storage_backend = "local"
    storage_location = str(Path(local_path).resolve())
else:
    if not mongo_url:
        raise RuntimeError(
            "MONGO_URL não foi configurado. Para testar sem MongoDB, use STORAGE_DRIVER=local."
        )

    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError(
            "O pacote pymongo não está instalado. Execute: pip install -r requirements.txt"
        ) from exc

    timeout_ms = int(os.getenv("MONGO_TIMEOUT_MS", "10000"))
    client = MongoClient(
        mongo_url,
        serverSelectionTimeoutMS=timeout_ms,
        connectTimeoutMS=timeout_ms,
        socketTimeoutMS=max(timeout_ms, 20000),
        uuidRepresentation="standard",
    )
    try:
        client.admin.command("ping")
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível conectar ao MongoDB. Verifique MONGO_URL, usuário, senha e IP liberado."
        ) from exc

    database = client[database_name]
    collection = database[f"bot_{bot_id}"]
    storage_backend = "mongo"
    storage_location = f"{database_name}.bot_{bot_id}"


def get_storage_info() -> dict[str, str]:
    return {
        "driver": storage_backend,
        "location": storage_location,
        "database": database_name if storage_backend == "mongo" else "local-json",
    }
