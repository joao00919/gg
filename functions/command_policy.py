from __future__ import annotations

import logging
import os
from typing import Iterable

logger = logging.getLogger("zynex.command_policy")


COMMAND_DESCRIPTIONS = {
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
    "set": "💰 | Vendas Moderação | Cadastra um novo produto no bot",
    "set_painel": "💰 | Vendas Moderação | Publique um painel já criado",
    "stockid": "📦 | Vendas Moderação | Veja o estoque de um produto",
    "sync_clients": "👥 | Vendas Moderação | Sincronize os cargos de clientes",
}


def _apply_command_descriptions(bot) -> None:
    """Garante que todos os comandos públicos apareçam com descrição no Discord."""
    for command in list(getattr(bot, "slash_commands", [])):
        description = COMMAND_DESCRIPTIONS.get(str(getattr(command, "name", "")))
        if not description:
            continue
        try:
            command.description = description
        except Exception:
            pass
        body = getattr(command, "body", None)
        if body is not None:
            try:
                body.description = description
            except Exception:
                pass

REQUIRED_SLASH_COMMANDS = frozenset({
    "anunciar", "botconfig", "cleardm", "conectar", "config", "config_painel",
    "configcupom", "criados", "criar", "criar_painel", "criarcupom", "dm",
    "entregar", "estatisticas", "gerarpix", "nuke", "perfil",
    "qrcode_personalizar", "rank", "rankprodutos", "resetar", "set",
    "set_painel", "stockid", "sync_clients",
})


def _enabled() -> bool:
    return os.getenv("ZYNEX_STRICT_COMMAND_SET", "true").strip().lower() in {"1", "true", "yes", "sim", "on"}


def _names(commands: Iterable[object]) -> set[str]:
    return {str(getattr(command, "name", "")) for command in commands if getattr(command, "name", None)}


def enforce_command_policy(bot) -> dict:
    """Mantém somente o conjunto público solicitado, sem apagar cogs ou código legado."""
    _apply_command_descriptions(bot)
    before = _names(getattr(bot, "slash_commands", []))
    removed: list[str] = []
    if _enabled():
        for command in list(getattr(bot, "slash_commands", [])):
            if command.name not in REQUIRED_SLASH_COMMANDS:
                bot.remove_slash_command(command.name)
                removed.append(command.name)
        for command in list(getattr(bot, "user_commands", [])):
            bot.remove_user_command(command.name)
        for command in list(getattr(bot, "message_commands", [])):
            bot.remove_message_command(command.name)

    after = _names(getattr(bot, "slash_commands", []))
    missing = sorted(REQUIRED_SLASH_COMMANDS - after)
    unexpected = sorted(after - REQUIRED_SLASH_COMMANDS) if _enabled() else []
    if missing:
        raise RuntimeError(f"Comandos obrigatórios não registrados: {', '.join(missing)}")
    if unexpected:
        raise RuntimeError(f"Comandos não autorizados registrados: {', '.join(unexpected)}")
    logger.info("Política de comandos aplicada | antes=%s | removidos=%s | ativos=%s", len(before), len(removed), len(after))
    return {"strict": _enabled(), "before": sorted(before), "removed": sorted(removed), "active": sorted(after)}
