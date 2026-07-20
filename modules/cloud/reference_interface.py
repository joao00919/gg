from __future__ import annotations

import disnake

from functions.database import database as db
from functions.emoji import emoji


def _em(name: str, fallback: str):
    return getattr(emoji, name, None) or fallback


def oauth_snapshot(inter: disnake.Interaction, bot) -> dict:
    conf = db.get_document("cloud_data") or {}
    enabled = bool(conf.get("oauth_enabled", conf.get("verification_mode") == "oauth"))
    configured = bool(conf.get("client_id"))
    active = enabled and configured
    log_channel_id = conf.get("log_channel_id")
    count = int(conf.get("oauth_member_count", 0) or 0)
    try:
        if inter.guild:
            from .local_verification import count_locally_verified
            count = max(count, int(count_locally_verified(inter.guild)))
    except Exception:
        pass
    bot_name = getattr(getattr(bot, "user", None), "name", None) or "Aplicação não identificada"
    return {
        "conf": conf,
        "enabled": enabled,
        "configured": configured,
        "active": active,
        "log_channel": f"<#{int(log_channel_id)}>" if log_channel_id else "`Não definido`",
        "count": count,
        "bot_name": bot_name,
    }


def components(inter: disnake.Interaction, bot):
    snap = oauth_snapshot(inter, bot)
    colors = db.get_document("custom_colors") or {}
    kwargs = {}
    if colors.get("primary"):
        try:
            kwargs["accent_colour"] = disnake.Colour(int(str(colors["primary"]).replace("#", ""), 16))
        except Exception:
            pass

    status = "Ativado" if snap["active"] else "Desativado"
    toggle_label = "Desligar Sistema" if snap["enabled"] else "Ativar Sistema"
    toggle_style = disnake.ButtonStyle.red if snap["enabled"] else disnake.ButtonStyle.green
    description = (
        "Configure a autenticação OAuth2 e recupere membros autorizados com segurança.\n"
        "O sistema utiliza as credenciais cadastradas no ZenyxClous."
    )
    details = (
        f"{_em('robot', '🤖')} **Seu Bot OAuth2:** `{snap['bot_name']}`\n"
        f"{_em('members', '👥')} **Membros OAuth2:** `{snap['count']} Usuários`\n"
        f"{_em('textc', '📝')} **Canal de Logs:** {snap['log_channel']}\n"
        f"{_em('power', '⏻')} **Status do Sistema:** `{status}`"
    )

    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {_em('zenyx2', 'Z')}\n-# Painel > ZenyxClous > **Autenticação OAuth2**"),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.TextDisplay(description),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.TextDisplay(details),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.ActionRow(
            disnake.ui.Button(label=toggle_label, style=toggle_style, emoji=_em('power', '⏻'), custom_id='Cloud_ToggleSystem'),
            disnake.ui.Button(label='Recuperar Membros', style=disnake.ButtonStyle.green, emoji=_em('reload', '🔄'), custom_id='Cloud_RecoverMembers', disabled=not snap['active']),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label='Mensagem OAuth2', style=disnake.ButtonStyle.grey, emoji=_em('message', '💬'), custom_id='Cloud_DefinirMensagens'),
            disnake.ui.Button(label='Definir canal de Logs', style=disnake.ButtonStyle.grey, emoji=_em('textc', '📝'), custom_id='Cloud_DefinirLogs'),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label='Adicionar Aplicação', style=disnake.ButtonStyle.link, emoji=_em('plus', '➕'), url='https://discord.com/developers/applications'),
            disnake.ui.Button(label='Credenciais OAuth2', style=disnake.ButtonStyle.grey, emoji=_em('settings', '⚙️'), custom_id='Cloud_ConfigurarCredenciais'),
            disnake.ui.Button(label='Desvincular OAuth2', style=disnake.ButtonStyle.red, emoji=_em('delete', '🗑️'), custom_id='Cloud_UnlinkOAuth', disabled=not snap['configured']),
        ),
        **kwargs,
    )
    return [container, disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=_em('back', '↩️'), custom_id='PainelInicial'))]


def embed(inter: disnake.Interaction, bot):
    snap = oauth_snapshot(inter, bot)
    status = "Ativado" if snap["active"] else "Desativado"
    emb = disnake.Embed(
        title="Autenticação OAuth2",
        description=(
            "Configure a autenticação OAuth2 e recupere membros autorizados com segurança.\n\n"
            f"**Seu Bot OAuth2:** `{snap['bot_name']}`\n"
            f"**Membros OAuth2:** `{snap['count']} Usuários`\n"
            f"**Canal de Logs:** {snap['log_channel']}\n"
            f"**Status do Sistema:** `{status}`"
        ),
    )
    colors = db.get_document("custom_colors") or {}
    if colors.get("primary"):
        try:
            emb.color = int(str(colors["primary"]).replace("#", ""), 16)
        except Exception:
            pass
    toggle_label = "Desligar Sistema" if snap["enabled"] else "Ativar Sistema"
    toggle_style = disnake.ButtonStyle.red if snap["enabled"] else disnake.ButtonStyle.green
    rows = [
        disnake.ui.ActionRow(
            disnake.ui.Button(label=toggle_label, style=toggle_style, emoji=_em('power', '⏻'), custom_id='Cloud_ToggleSystem'),
            disnake.ui.Button(label='Recuperar Membros', style=disnake.ButtonStyle.green, emoji=_em('reload', '🔄'), custom_id='Cloud_RecoverMembers', disabled=not snap['active']),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label='Mensagem OAuth2', style=disnake.ButtonStyle.grey, emoji=_em('message', '💬'), custom_id='Cloud_DefinirMensagens'),
            disnake.ui.Button(label='Definir canal de Logs', style=disnake.ButtonStyle.grey, emoji=_em('textc', '📝'), custom_id='Cloud_DefinirLogs'),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label='Adicionar Aplicação', style=disnake.ButtonStyle.link, emoji=_em('plus', '➕'), url='https://discord.com/developers/applications'),
            disnake.ui.Button(label='Credenciais OAuth2', style=disnake.ButtonStyle.grey, emoji=_em('settings', '⚙️'), custom_id='Cloud_ConfigurarCredenciais'),
            disnake.ui.Button(label='Desvincular OAuth2', style=disnake.ButtonStyle.red, emoji=_em('delete', '🗑️'), custom_id='Cloud_UnlinkOAuth', disabled=not snap['configured']),
        ),
        disnake.ui.ActionRow(disnake.ui.Button(label='Voltar', style=disnake.ButtonStyle.grey, emoji=_em('back', '↩️'), custom_id='PainelInicial')),
    ]
    return emb, rows
