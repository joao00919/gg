"""Valida offline a aba Configurar Loja e suas rotas principais."""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace


class FakeResponse:
    def __init__(self):
        self.done = False
        self.actions = []

    def is_done(self):
        return self.done

    async def send_message(self, *args, **kwargs):
        self.done = True
        self.actions.append(("send", args, kwargs))

    async def edit_message(self, *args, **kwargs):
        self.done = True
        self.actions.append(("edit", args, kwargs))

    async def defer(self, *args, **kwargs):
        self.done = True
        self.actions.append(("defer", args, kwargs))

    async def send_modal(self, modal, *args, **kwargs):
        self.done = True
        self.actions.append(("modal", (modal,), kwargs))


class FakeFollowup:
    def __init__(self):
        self.actions = []

    async def send(self, *args, **kwargs):
        self.actions.append((args, kwargs))
        return SimpleNamespace()


class FakeInteraction:
    def __init__(self, bot, custom_id: str, values=None):
        self.bot = bot
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.component = SimpleNamespace(custom_id=custom_id)
        self.values = list(values or [])
        self.user = self.author = SimpleNamespace(
            id=1,
            name="Teste",
            display_name="Teste",
            roles=[],
            guild_permissions=SimpleNamespace(administrator=True),
        )
        self.guild = SimpleNamespace(
            id=123456789012345678,
            owner_id=1,
            name="Servidor",
            icon=None,
            roles=[],
            channels=[],
            get_member=lambda _id: None,
            get_role=lambda _id: None,
            get_channel=lambda _id: None,
        )
        self.guild_id = self.guild.id
        self.channel = SimpleNamespace(id=10, name="teste")
        self.channel_id = 10
        self.message = SimpleNamespace(flags=SimpleNamespace(ephemeral=True))
        self.edits = []

    async def edit_original_response(self, **kwargs):
        self.edits.append(kwargs)

    async def edit_original_message(self, **kwargs):
        self.edits.append(kwargs)


async def run() -> int:
    with tempfile.TemporaryDirectory(prefix="zenyx-store-4318-") as temp_dir:
        os.environ.update(
            STORAGE_DRIVER="local",
            LOCAL_DATABASE_PATH=str(Path(temp_dir) / "database.json"),
            MAIN_GUILD_ID="123456789012345678",
            DISCORD_TEST_GUILD_ID="123456789012345678",
            DISCORD_CLIENT_ID="123456789012345678",
            DISCORD_TOKEN="MTIzNDU2Nzg5MDEyMzQ1Njc4.fake.fake",
            ZYNEX_MIGRATION_BACKUP="false",
            BOT_PLAN="pro",
        )
        from functions.database import database
        database.initialize_database_if_needed()
        database.verify_and_create_missing_documents()

        import core
        from bot import _load_extensions

        bot, _token, _application_id = core.create_bot()
        _load_extensions(bot)

        loja = bot.get_cog("Loja")
        produtos = bot.get_cog("GerenciarProdutos")
        if loja is None or produtos is None:
            raise RuntimeError("Cogs da loja não foram carregados")

        for choice in ("produtos", "personalizar", "preferencias", "extensoes", "saldo", "cashback", "afiliados"):
            inter = FakeInteraction(bot, "Loja_Select", [choice])
            await loja.on_dropdown(inter)
            if not inter.response.done:
                raise RuntimeError(f"Loja_Select/{choice}: interação não reconhecida")
            print(f"[OK] Loja_Select -> {choice}")

        toggle = FakeInteraction(bot, "Loja_ToggleSales")
        await loja.on_button_click(toggle)
        if not toggle.response.done:
            raise RuntimeError("Desligar/Ligar vendas não respondeu")
        print("[OK] Ligar/Desligar Vendas")

        templates = FakeInteraction(bot, "Loja_Templates")
        await loja.on_button_click(templates)
        if not templates.response.done:
            raise RuntimeError("Templates não respondeu")
        print("[OK] Templates")

        create_panel = FakeInteraction(bot, "Loja_CriarPainel")
        await produtos.on_button_click(create_panel)
        if not create_panel.response.done or not any(action[0] == "modal" for action in create_panel.response.actions):
            raise RuntimeError("Criar Painel não abriu modal")
        print("[OK] Criar Painel")

        await bot.close()
        print("RESULTADO: aba Configurar Loja validada sem interações expiradas.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
