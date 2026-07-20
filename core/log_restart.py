from __future__ import annotations

import os
import time
from typing import Iterable, Optional

import disnake

from functions.database import database
from functions.emoji import emoji


def _numeric_id(*values) -> Optional[int]:
    for value in values:
        text = str(value or "").strip()
        if text.isdigit():
            return int(text)
    return None


def _can_announce(channel: disnake.abc.GuildChannel, guild: disnake.Guild) -> bool:
    if not isinstance(channel, (disnake.TextChannel, disnake.Thread)):
        return False
    member = guild.me
    if member is None:
        return False
    perms = channel.permissions_for(member)
    return bool(perms.view_channel and perms.send_messages and perms.embed_links)


def _target_guilds(bot: disnake.Client, config: dict) -> Iterable[disnake.Guild]:
    guild_id = _numeric_id(
        os.getenv("LICENSE_GUILD_ID"),
        os.getenv("GUILD_ID"),
        os.getenv("DISCORD_GUILD_ID"),
        (config.get("bot") or {}).get("server"),
    )
    if guild_id:
        guild = bot.get_guild(guild_id)
        return [guild] if guild else []
    return list(bot.guilds)


def _resolve_channel(bot: disnake.Client, guild: disnake.Guild, channels_data: dict):
    """Usa somente o canal definido pelo cliente para logs do sistema."""
    candidate_ids = [
        _numeric_id(os.getenv("RESTART_NOTICE_CHANNEL_ID")),
        _numeric_id(channels_data.get("canal_de_logs_do_sistema")),
    ]
    for channel_id in candidate_ids:
        if not channel_id:
            continue
        channel = bot.get_channel(channel_id) or guild.get_channel(channel_id)
        if channel and getattr(channel, "guild", None) == guild and _can_announce(channel, guild):
            return channel
    return None


async def log_restart(bot: disnake.Client):
    """Avisa, no servidor do cliente, que a reinicialização terminou com sucesso."""
    try:
        info = database.obter("config.json") or {}
        channels_data = database.get_document("canais") or {}
        colors = database.get_document("custom_colors") or {}
        brand = os.getenv("BRAND_NAME", "ZYNEX Systems").strip() or "ZYNEX Systems"
        version = str(info.get("version") or "4.3.18")
        timestamp = int(time.time())

        color = disnake.Color.from_rgb(25, 26, 29)
        primary = str(colors.get("primary") or "").replace("#", "")
        if primary:
            try:
                color = disnake.Color(int(primary, 16))
            except ValueError:
                pass

        for guild in _target_guilds(bot, info):
            channel = _resolve_channel(bot, guild, channels_data)
            if channel is None:
                print(f"[RESTART] Canal não configurado em {guild.name} ({guild.id}). Use /botconfig > Configurações > Canais > Logs do Sistema e Reinicializações.")
                continue

            embed = disnake.Embed(
                title=f"{emoji.online} Bot reiniciado com sucesso",
                description=(
                    f"{emoji.correct} O **{brand}** voltou a ficar online e está pronto para receber comandos, vendas e atendimentos.\n\n"
                    f"{emoji.robot} **Versão:** `{version}`\n"
                    f"{emoji.calendar} **Reiniciado em:** <t:{timestamp}:F>\n"
                    f"{emoji.online} **Conexão:** `Online`\n"
                    f"{emoji.correct} **Serviços:** `Operacionais`"
                ),
                color=color,
            )
            embed.set_footer(text="Canal escolhido em /botconfig > Configurações > Canais")

            components = None
            support_url = os.getenv("SUPPORT_URL", "").strip()
            if support_url.startswith("https://"):
                components = [disnake.ui.ActionRow(disnake.ui.Button(
                    label="Central de suporte",
                    emoji=emoji.relations,
                    style=disnake.ButtonStyle.link,
                    url=support_url,
                ))]
            await channel.send(
                embed=embed,
                components=components,
                allowed_mentions=disnake.AllowedMentions.none(),
            )
    except Exception as exc:
        print(f"[RESTART] Falha ao enviar aviso de reinicialização: {exc}")
