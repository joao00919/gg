from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from functions.command_policy import REQUIRED_SLASH_COMMANDS

ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _walk(node):
    yield node
    for child in node.get("components", []) or []:
        yield from _walk(child)


def _nodes(items):
    if isinstance(items, dict):
        items = items.get("components", [])
    for item in items:
        yield from _walk(item.to_component_dict())


def _labels(items):
    return [node["label"] for node in _nodes(items) if node.get("label")]


def _options(items):
    result = []
    for node in _nodes(items):
        result.extend(option.get("label") for option in node.get("options", []) or [])
    return [value for value in result if value]


def _slash_descriptions() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in (ROOT / "commands").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "slash_command"
                ):
                    continue
                kwargs = {item.arg: item.value for item in decorator.keywords if item.arg}
                name = kwargs.get("name")
                description = kwargs.get("description")
                if isinstance(name, ast.Constant) and isinstance(description, ast.Constant):
                    found[str(name.value)] = str(description.value)
    return found


def test_public_command_contract_matches_uploaded_video():
    descriptions = _slash_descriptions()
    assert set(REQUIRED_SLASH_COMMANDS) <= descriptions.keys()
    assert len(REQUIRED_SLASH_COMMANDS) == 25
    expected = {
        "anunciar": "🖊️ | Moderação | Enviar um anúncio para todos os membros.",
        "botconfig": "💰 | Vendas e Moderação | Configurar as opções do bot.",
        "cleardm": "🛠️ | Utilidades | Limpe todas as mensagens do bot na sua DM!",
        "conectar": "🛠️ | Vendas Moderação | Faz o bot entrar em um canal de voz",
        "config": "💰 | Vendas Moderação | Configure um produto",
        "config_painel": "💰 | Vendas Moderação | Configure um painel",
        "configcupom": "🛠️💰 | Vendas Moderação | Configure um cupom",
        "criados": "💰 | Vendas Moderação | Veja os itens cadastrados no bot",
        "criar": "💰 | Vendas Moderação | Cadastra um novo produto no bot",
        "criar_painel": "💰 | Vendas Moderação | Crie um painel select menu para seus produtos",
        "criarcupom": "💰 | Vendas Moderação | Crie um cupom de desconto",
        "dm": "🛠️ | Moderação | Envie uma mensagem no privado de um usuário",
        "entregar": "💰 | Vendas Moderação | Entrega manual de produtos para um membro",
        "estatisticas": "📊 | Vendas Moderação | Veja as estatísticas de vendas do bot",
        "gerarpix": "🪙 | Vendas | Gere uma cobrança",
        "nuke": "🛠️ | Moderação | Limpa o canal atual recriando-o",
        "perfil": "💰 | Vendas | Exibe o perfil de compras de um membro",
        "qrcode_personalizar": "💰 | Vendas Moderação | Personalize seu QR Code de pagamentos",
        "rank": "🏆 | Vendas | Exibe o ranking de compradores da loja",
        "rankprodutos": "🏆 | Vendas | Veja os produtos que mais geraram lucro",
        "resetar": "🛠️💰 | Vendas Moderação | Resete vendas, ranking e cupons",
        "set": "💰 | Vendas Moderação | Publique um produto já criado",
        "set_painel": "💰 | Vendas Moderação | Publique um painel já criado",
        "stockid": "📦 | Vendas Moderação | Veja o estoque de um produto",
        "sync_clients": "👥 | Vendas Moderação | Sincronize os cargos de clientes",
    }
    assert {name: descriptions[name] for name in expected} == expected
    assert all(1 <= len(value) <= 100 for value in expected.values())


def test_announcement_editor_matches_video_text_and_actions():
    module = _load_module("commands/admin/anunciar/anunciar.py", "video_contract_anunciar")
    empty = {
        "message": {
            "content": "Mensagem",
            "container": None,
            "externalImage": "https://example.com/banner.png",
            "buttons": [{"label": "Comprar"}],
            "embed": {"title": None, "description": None, "color": None, "footer": None},
        }
    }
    with patch.object(module.database, "get_document", return_value=empty):
        items = module.Anunciar.create_buttons()
    assert _labels(items) == [
        "Definir Mensagem",
        "Definir Container",
        "Definir Embed",
        "Definir Imagens",
        "Definir Botões",
        "Apagar Tudo",
        "Visualizar",
        "Postar",
        "Salvar Template",
        "Templates Salvos",
    ]
    rendered = json.dumps([item.to_component_dict() for item in items], ensure_ascii=False)
    assert "Crie, personalize e anuncie mensagens em canais." in rendered
    assert "Aplique e salve templates de mensagens." in rendered


def test_main_store_and_ticket_navigation_contract():
    painel_module = _load_module("commands/admin/painel.py", "video_contract_painel")
    states = {name: True for name in (
        "loja", "ticket", "cloud", "rendimentos", "personalizacao",
        "automacoes", "protection", "sorteios", "configuracoes",
    )}
    main = painel_module.PainelCommand(None).PainelComponents(
        SimpleNamespace(user=SimpleNamespace(name="Cliente")),
        button_states=states,
    )
    assert _labels(main) == [
        "Configurar Loja", "Gerenciar Ticket", "ZenyxClous",
        "Proteção do Servidor", "Automações", "Configurações", "Sorteios",
    ]

    from modules.loja.cog import Loja
    with (
        patch("modules.loja.cog.db.get_document", side_effect=lambda name: {"mode": "components"} if name == "custom_mode" else {}),
        patch("modules.loja.cog.sales_enabled", return_value=True),
    ):
        store = Loja(None).panel(SimpleNamespace())
    assert _options(store) == [
        "Gerenciar Produtos", "Personalizar Loja", "Preferências", "Extensões",
        "Sistema de Saldo", "Cashback", "Programa de Indicação",
    ]

    from modules.tickets.config.config_ticket import PainelTicket_components
    ticket_store = {"tickets_config": {"panels": {"P1": {"name": "Suporte", "enabled": True}}}, "custom_colors": {}}
    with patch(
        "modules.tickets.config.config_ticket.db.get_document",
        side_effect=lambda name: ticket_store.get(name, {}),
    ):
        ticket = PainelTicket_components(SimpleNamespace())
    assert _labels(ticket) == ["Desligar Todos", "Criar Painel", "Editar Painel", "Voltar"]


def test_runtime_safety_is_installed_before_extensions():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    run_body = source[source.index("def _run_bot()"):]
    safety_call = run_body.index("install_discord_runtime_safety()")
    extension_call = run_body.index("_load_extensions(bot)")
    assert safety_call < extension_call
    assert "install_discord_runtime_safety(bot)" in source
