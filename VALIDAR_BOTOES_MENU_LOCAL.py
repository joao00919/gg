"""Valida offline todos os botões do menu principal do ZENYX 4.3.18.

Não conecta ao Discord. Carrega o projeto com banco temporário, aciona as rotas
reais do menu e confirma que cada interação foi reconhecida e produziu um painel.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace


class FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.actions: list[tuple[str, tuple, dict]] = []

    def is_done(self) -> bool:
        return self.done

    async def send_message(self, *args, **kwargs):
        self.done = True
        self.actions.append(("send", args, kwargs))

    async def defer(self, *args, **kwargs):
        self.done = True
        self.actions.append(("defer", args, kwargs))

    async def edit_message(self, *args, **kwargs):
        self.done = True
        self.actions.append(("edit", args, kwargs))

    async def send_modal(self, *args, **kwargs):
        self.done = True
        self.actions.append(("modal", args, kwargs))


class FakeFollowup:
    def __init__(self) -> None:
        self.actions: list[tuple[tuple, dict]] = []

    async def send(self, *args, **kwargs):
        self.actions.append((args, kwargs))
        return SimpleNamespace()


class FakeInteraction:
    def __init__(self, bot, custom_id: str) -> None:
        self.bot = bot
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.component = SimpleNamespace(custom_id=custom_id)
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
            name="Servidor de teste",
            icon=None,
            roles=[],
            channels=[],
            get_member=lambda _id: None,
            get_role=lambda _id: None,
            get_channel=lambda _id: None,
        )
        self.guild_id = self.guild.id
        self.channel_id = 10
        self.channel = SimpleNamespace(id=10, name="teste")
        self.message = SimpleNamespace(flags=SimpleNamespace(ephemeral=True))
        self.edits: list[dict] = []

    async def edit_original_response(self, **kwargs):
        self.edits.append(kwargs)

    async def edit_original_message(self, **kwargs):
        self.edits.append(kwargs)

    async def delete_original_message(self):
        return None


def _flatten_components(items):
    for item in items or []:
        yield item
        children = getattr(item, "children", None)
        if children:
            yield from _flatten_components(children)


async def run() -> int:
    with tempfile.TemporaryDirectory(prefix="zenyx-menu-4318-") as temp_dir:
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

        # A consulta real do Cloud pode depender de rede. O teste valida a rota e
        # o painel sem fazer chamada externa.
        import modules.cloud.cog as cloud_module

        async def fake_cloud_status(_inter):
            return "Disponível para configuração."

        cloud_module.helpers.get_status_text = fake_cloud_status

        painel = bot.get_cog("PainelCommand")
        if painel is None:
            raise RuntimeError("PainelCommand não foi carregado")

        buttons = {
            "Painel_Loja": "Configurar Loja",
            "Painel_Ticket": "Gerenciar Ticket",
            "Painel_Cloud": "ZenyxClous",
            "Painel_Protection": "Proteção do Servidor",
            "Painel_Automacoes": "Automações",
            "Painel_Configuracoes": "Configurações",
            "Painel_Sorteios": "Sorteios",
        }

        for custom_id, label in buttons.items():
            inter = FakeInteraction(bot, custom_id)
            await painel.Painel_Button_Listener(inter)
            if not inter.response.done:
                raise RuntimeError(f"{label}: interação não reconhecida")
            if not (inter.response.actions or inter.edits or inter.followup.actions):
                raise RuntimeError(f"{label}: nenhum painel ou mensagem produzido")
            print(f"[OK] {label}")

        # Confere o botão Formas de Pagamento e a remoção de Promisse Wallet.
        payments = bot.get_cog("ConfigurarPagamentos")
        if payments is None:
            raise RuntimeError("ConfigurarPagamentos não foi carregado")
        pay_inter = FakeInteraction(bot, "Configuracoes_Pagamentos")
        await payments.on_button_click(pay_inter)
        if not pay_inter.response.done:
            raise RuntimeError("Formas de Pagamento: interação não reconhecida")

        components = payments.pagamentos_components(pay_inter)
        labels = []
        for item in _flatten_components(components):
            for option in getattr(item, "options", None) or []:
                labels.append(str(option.label))
        if "Promisse Wallet" in labels:
            raise RuntimeError("Promisse Wallet ainda aparece nas formas de pagamento")
        print("[OK] Formas de Pagamento sem Promisse Wallet")

        await bot.close()
        print("RESULTADO: todos os botões principais responderam corretamente.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
