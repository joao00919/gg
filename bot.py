from __future__ import annotations

import argparse
import asyncio
import compileall
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# O .env deve ser carregado antes dos módulos que selecionam o banco de dados.
load_dotenv()

from runtime_logging import configure_logging
from functions.database import database

logger = logging.getLogger("zynex.startup")
VERSION = "4.3.18"
BRAND = "ZYNEX Systems"


def _enabled(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _bootstrap_storage() -> dict:
    database.initialize_database_if_needed()
    database.verify_and_create_missing_documents()
    from migrations.zynex_no_api import run_migrations
    migration = run_migrations(create_backup=_enabled("ZYNEX_MIGRATION_BACKUP", True))
    if migration.get("applied"):
        logger.info("Migração aplicada: %s", migration.get("migration"))
    health = database.health_check()
    if not health.get("ok"):
        raise RuntimeError(f"Falha no armazenamento: {health.get('error', 'erro desconhecido')}")
    logger.info(
        "Armazenamento pronto | driver=%s | local=%s",
        health.get("driver"),
        health.get("location"),
    )
    return health


def _validate_python_sources() -> None:
    project_root = Path(__file__).resolve().parent
    ok = compileall.compile_dir(
        project_root,
        quiet=1,
        force=True,
        rx=re.compile(r"[\\/](?:\.venv|venv|__pycache__|data)[\\/]"),
    )
    if not ok:
        raise RuntimeError(
            "Há arquivos Python com erro de sintaxe. Veja as linhas exibidas acima."
        )


def _configuration_check() -> int:
    _validate_python_sources()
    health = _bootstrap_storage()
    from core.create_bot import resolve_discord_client_id, resolve_discord_token

    diagnostic_token = resolve_discord_token()
    token_ok = bool(diagnostic_token)
    try:
        diagnostic_client_id = resolve_discord_client_id(diagnostic_token) if diagnostic_token else ""
    except RuntimeError:
        diagnostic_client_id = ""
    app_id_ok = bool(diagnostic_client_id)

    print(f"\n=== {BRAND} - diagnóstico local ===")
    print(f"Versão: {VERSION}")
    print(f"Armazenamento: OK ({health.get('driver')})")
    print(f"Local: {health.get('location')}")
    print(f"DISCORD_TOKEN/BOT_TOKEN: {'configurado' if token_ok else 'não configurado'}")
    print(f"DISCORD_CLIENT_ID: {'configurado/identificado automaticamente' if app_id_ok else 'não identificado'}")
    print("Sintaxe Python: OK")
    print("Arquivos essenciais: OK")
    print("Resultado: ambiente local validado sem necessidade de MongoDB.\n")
    return 0


def _load_extensions(bot) -> None:
    # Também instala aqui para validadores locais que chamam _load_extensions
    # diretamente sem executar _run_bot. A função é idempotente.
    from functions.discord_runtime_safety import install_discord_runtime_safety
    install_discord_runtime_safety(bot)
    extensions = ("modules", "commands", "events", "tasks")
    for extension in extensions:
        try:
            bot.load_extension(extension)
            logger.info("Extensão carregada: %s", extension)
        except Exception:
            logger.exception("Falha ao carregar a extensão: %s", extension)
            raise


def _run_bot() -> int:
    # Python 3.12 não cria mais um event loop automaticamente na thread principal.
    # Algumas extensões do disnake iniciam tasks durante o carregamento e precisam
    # que o loop já exista antes de bot.load_extension(...).
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    import core
    from core.server_protection import apply_server_protection
    from functions.emoji import init_on_startup
    from functions.discord_runtime_safety import install_discord_runtime_safety

    # Instala as correções antes de carregar qualquer extensão que construa modais.
    install_discord_runtime_safety()
    _bootstrap_storage()
    bot, token, application_id = core.create_bot()
    install_discord_runtime_safety(bot)

    # Mantém o mesmo catálogo visual em qualquer aplicação Discord. O antigo
    # SYNC_APPLICATION_EMOJIS=false não desativa silenciosamente a identidade do bot;
    # para manutenção técnica existe a opção explícita abaixo.
    if _enabled("DISABLE_APPLICATION_EMOJI_SYNC", False):
        logger.warning("Sincronização de emojis desativada por DISABLE_APPLICATION_EMOJI_SYNC=true.")
    else:
        if not _enabled("SYNC_APPLICATION_EMOJIS", True):
            logger.warning("SYNC_APPLICATION_EMOJIS=false é uma opção antiga; a sincronização segura será mantida.")
        init_on_startup(token, application_id)

    apply_server_protection(bot)
    _load_extensions(bot)

    from functions.command_policy import enforce_command_policy
    command_report = enforce_command_policy(bot)
    logger.info("Comandos públicos ativos: %s", ", ".join(command_report["active"]))

    logger.info("Iniciando %s %s...", BRAND, VERSION)
    logger.info("Ative Member Intent e Message Content Intent manualmente no Developer Portal.")
    bot.run(token)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ZYNEX Systems — bot de vendas")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Valida arquivos e armazenamento local sem conectar ao Discord.",
    )
    parser.add_argument(
        "--reset-local-data",
        action="store_true",
        help="Apaga o banco JSON local antes do diagnóstico.",
    )
    args = parser.parse_args()

    configure_logging()

    if args.reset_local_data:
        if os.getenv("STORAGE_DRIVER", "auto").lower() == "mongo":
            logger.error("--reset-local-data não pode ser usado com STORAGE_DRIVER=mongo.")
            return 2
        path = Path(os.getenv("LOCAL_DATABASE_PATH", "data/local_database.json"))
        if path.exists():
            path.unlink()
            logger.info("Banco local removido: %s", path)

    try:
        return _configuration_check() if args.check else _run_bot()
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário.")
        return 0
    except Exception as exc:
        logger.error("Inicialização interrompida: %s", exc)
        if _enabled("DEBUG", False):
            logger.exception("Detalhes técnicos")
        else:
            logger.error("Use DEBUG=true no .env para exibir o traceback completo.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
