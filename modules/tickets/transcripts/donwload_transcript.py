"""Geração, hospedagem e entrega do transcript pela DM."""

from __future__ import annotations

import io
import os

import disnake

from functions.database import database as db
from functions.emoji import emoji
from functions.transcript_cache import get_cached_link, save_link_to_cache
from .host_transcript import upload_transcript_to_api


def _ttl_text() -> str:
    try:
        hours = max(1, int(os.getenv("TRANSCRIPT_TTL_HOURS", "72")))
    except ValueError:
        hours = 72
    if hours % 24 == 0:
        days = hours // 24
        return f"{days} dia" if days == 1 else f"{days} dias"
    return f"{hours} horas"


async def send_transcript_to_dm(
    interaction: disnake.ApplicationCommandInteraction,
    transcript_file: disnake.File,
):
    """Sempre entrega o HTML; a versão online é adicionada quando disponível."""
    config = db.get_document("tickets_config") or {}
    tickets_data = db.get_document("tickets_data") or {}

    panel_id = None
    if isinstance(interaction.channel, (disnake.TextChannel, disnake.Thread)):
        for pid, users in (tickets_data.get("panels") or {}).items():
            if any(
                int(ticket.get("ticket_id") or 0) == interaction.channel.id
                for tickets in (users or {}).values()
                for ticket in tickets or []
            ):
                panel_id = pid
                break

    panel_data = (config.get("panels") or {}).get(panel_id, {}) if panel_id else {}
    template = (panel_data.get("messages") or {}).get(
        "transcript_dm_message",
        "Aqui está o transcript solicitado para o ticket `{channel_name}`:",
    )
    template = str(template).replace("<:online:1525583691491836076>", str(emoji.online))
    message_content = template.format(
        channel_name=interaction.channel.name,
        guild_name=interaction.guild.name,
        user_mention=interaction.author.mention,
        user_name=interaction.author.name,
    )

    try:
        transcript_file.fp.seek(0)
        html_bytes = transcript_file.fp.read()
        if isinstance(html_bytes, str):
            html_bytes = html_bytes.encode("utf-8")
        transcript_html = html_bytes.decode("utf-8", errors="replace")

        transcript_url = get_cached_link(interaction.channel.id)
        if not transcript_url:
            transcript_url = await upload_transcript_to_api(
                transcript_html, interaction.channel.name
            )
            if transcript_url:
                save_link_to_cache(interaction.channel.id, transcript_url)

        embed = disnake.Embed(
            title=f"{emoji.online} Transcript do atendimento",
            description=(
                "O arquivo HTML completo está anexado nesta mensagem."
                + (
                    " A versão online pode ser aberta pelo botão abaixo."
                    if transcript_url
                    else " A hospedagem online está indisponível no momento, mas o arquivo permanece acessível."
                )
            ),
            color=disnake.Color.from_rgb(25, 26, 29),
        )
        if transcript_url:
            embed.add_field(
                name="Disponibilidade online",
                value=f"O link hospedado expira em aproximadamente **{_ttl_text()}**.",
                inline=False,
            )

        components = None
        if transcript_url:
            components = [disnake.ui.ActionRow(disnake.ui.Button(
                label="Abrir transcript online",
                emoji=emoji.receipt,
                style=disnake.ButtonStyle.link,
                url=transcript_url,
            ))]

        await interaction.author.send(
            content=message_content,
            embed=embed,
            file=disnake.File(
                fp=io.BytesIO(html_bytes),
                filename=f"transcript-{interaction.channel.name}.html",
            ),
            components=components,
        )
        await interaction.followup.send(
            f"{emoji.double_check} Transcript HTML enviado para sua DM"
            + (" com o link online." if transcript_url else "."),
            ephemeral=True,
        )
    except disnake.Forbidden:
        await interaction.followup.send(
            f"{emoji.wrong} Não consegui enviar o transcript. Abra suas DMs e tente novamente.",
            ephemeral=True,
        )
    except Exception as exc:
        print(f"[TRANSCRIPT] Erro ao enviar transcript na DM: {exc}")
        await interaction.followup.send(
            f"{emoji.wrong} Ocorreu um erro ao processar o transcript.",
            ephemeral=True,
        )
