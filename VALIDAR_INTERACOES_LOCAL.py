"""Validação offline das interações críticas do ZENYX 4.3.18.

Não conecta ao Discord e não usa token real. Confere carregamento das extensões e
executa /botconfig, /qrcode_personalizar e /criar com interações simuladas.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent


class FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.sent: list[tuple[tuple, dict]] = []

    def is_done(self) -> bool:
        return self.done

    async def send_message(self, *args, **kwargs):
        self.done = True
        self.sent.append((args, kwargs))

    async def defer(self, *args, **kwargs):
        self.done = True

    async def send_modal(self, *args, **kwargs):
        self.done = True
        self.sent.append((args, kwargs))


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[tuple[tuple, dict]] = []

    async def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))
        return SimpleNamespace()


class FakeInteraction:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.user = self.author = SimpleNamespace(
            id=1,
            name="Teste",
            guild_permissions=SimpleNamespace(administrator=True),
        )
        self.guild = SimpleNamespace(
            id=123456789012345678,
            owner_id=1,
            name="Servidor de teste",
        )
        self.guild_id = self.guild.id
        self.channel_id = 10
        self.channel = SimpleNamespace(id=10, name="teste")
        self.edits: list[dict] = []

    async def edit_original_response(self, **kwargs):
        self.edits.append(kwargs)

    async def edit_original_message(self, **kwargs):
        self.edits.append(kwargs)


async def run() -> int:
    with tempfile.TemporaryDirectory(prefix="zenyx-4318-") as temp_dir:
        os.environ["STORAGE_DRIVER"] = "local"
        os.environ["LOCAL_DATABASE_PATH"] = str(Path(temp_dir) / "database.json")
        os.environ["MAIN_GUILD_ID"] = "123456789012345678"
        os.environ["DISCORD_TEST_GUILD_ID"] = "123456789012345678"
        os.environ["DISCORD_CLIENT_ID"] = "123456789012345678"
        os.environ["DISCORD_TOKEN"] = "MTIzNDU2Nzg5MDEyMzQ1Njc4.fake.fake"
        os.environ["ZYNEX_MIGRATION_BACKUP"] = "false"

        from functions.database import database

        database.initialize_database_if_needed()
        database.verify_and_create_missing_documents()

        import core
        from bot import _load_extensions

        bot, _token, application_id = core.create_bot()
        _load_extensions(bot)

        required_commands = ("botconfig", "qrcode_personalizar", "criar")
        for name in required_commands:
            if not bot.get_slash_command(name):
                raise RuntimeError(f"Comando ausente: /{name}")

        for name, args in (
            ("botconfig", ()),
            ("qrcode_personalizar", ()),
            ("criar", ("Produto de teste",)),
        ):
            command = bot.get_slash_command(name)
            inter = FakeInteraction(bot)
            await command.callback(command.cog, inter, *args)
            if not inter.response.done:
                raise RuntimeError(f"/{name} terminou sem reconhecer a interação")
            if not (inter.response.sent or inter.edits or inter.followup.sent):
                raise RuntimeError(f"/{name} não produziu mensagem ou painel")
            print(f"[OK] /{name} respondeu sem expirar")

        products = database.get_document("loja_products") or {}
        if not any(item.get("name") == "Produto de teste" for item in products.values()):
            raise RuntimeError("/criar não persistiu o produto")

        print(f"[OK] Extensões: {len(bot.cogs)} cogs e {len(bot.slash_commands)} comandos slash")
        print(f"[OK] Aplicação resolvida: {application_id}")
        print("RESULTADO: interações críticas validadas.")
        await bot.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
