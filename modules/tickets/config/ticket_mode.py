from __future__ import annotations

import disnake

from functions.database import database as db
from functions.emoji import emoji
from modules.tickets.purchase_link import TICKET_MODES, normalize_panel

_MODE_DESCRIPTIONS = {
    "common": "Atendimento geral, sem exigir compra.",
    "purchase": "O cliente precisa selecionar uma compra.",
    "mixed": "Permite selecionar uma compra ou abrir sem vínculo.",
    "warranty": "Mostra somente compras dentro da garantia.",
    "financial": "Atendimento financeiro sem vínculo obrigatório.",
}


def _select(panel_id: str, current: str) -> disnake.ui.StringSelect:
    options = []
    emoji_map = {
        "common": emoji.interrogation,
        "purchase": emoji.cardbox,
        "mixed": emoji.search,
        "warranty": emoji.unlock,
        "financial": emoji.coin,
    }
    for key, label in TICKET_MODES.items():
        options.append(
            disnake.SelectOption(
                label=label,
                value=key,
                description=_MODE_DESCRIPTIONS[key],
                emoji=emoji_map[key],
                default=key == current,
            )
        )
    return disnake.ui.StringSelect(
        custom_id=f"TicketMode_Select_{panel_id}",
        placeholder="Selecione o tipo de atendimento",
        min_values=1,
        max_values=1,
        options=options,
    )


def _description(panel: dict) -> str:
    panel = normalize_panel(panel)
    mode = panel["ticket_mode"]
    settings = panel["purchase_settings"]
    text = (
        f"{emoji.interrogation} **Tipo atual:** `{TICKET_MODES.get(mode, mode)}`\n"
        f"{emoji.cardbox} **Vínculo com compra:** "
        f"`{'Ativo' if mode in {'purchase', 'mixed', 'warranty'} else 'Desativado'}`\n"
        f"{emoji.calendar} **Garantia:** `{settings.get('warranty_days', 30)} dias`\n"
        f"{emoji.cardbox} **Compras exibidas:** `até {settings.get('max_purchases', 25)}`\n\n"
        "O vínculo é configurado por painel. Não são criados comandos separados de suporte."
    )
    return text


def TicketModeView_components(inter: disnake.Interaction, panel_id: str) -> list:
    config = db.get_document("tickets_config") or {}
    panel = (config.get("panels") or {}).get(panel_id, {})
    normalize_panel(panel)
    color = (db.get_document("custom_colors") or {}).get("primary")
    kwargs = {}
    if color:
        kwargs["accent_colour"] = disnake.Colour(int(color.replace("#", ""), 16))
    return [
        disnake.ui.Container(
            disnake.ui.TextDisplay(
                f"# {emoji.z0}\n-# Painel > Gerenciar Tickets > "
                f"{panel.get('name', 'Painel')} > **Tipo de Ticket**"
            ),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay(_description(panel)),
            disnake.ui.Separator(),
            disnake.ui.ActionRow(_select(panel_id, panel.get("ticket_mode", "common"))),
            **kwargs,
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Voltar",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.back,
                custom_id=f"TicketEdit_BackToPanel_{panel_id}",
            )
        ),
    ]


def TicketModeView_embed(inter: disnake.Interaction, panel_id: str):
    config = db.get_document("tickets_config") or {}
    panel = (config.get("panels") or {}).get(panel_id, {})
    normalize_panel(panel)
    color = (db.get_document("custom_colors") or {}).get("primary")
    kwargs = {"color": int(color.replace("#", ""), 16)} if color else {}
    embed = disnake.Embed(
        title="Tipo de Ticket",
        description=_description(panel),
        **kwargs,
    )
    components = [
        disnake.ui.ActionRow(_select(panel_id, panel.get("ticket_mode", "common"))),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Voltar",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.back,
                custom_id=f"TicketEdit_BackToPanel_{panel_id}",
            )
        ),
    ]
    return embed, components


def save_ticket_mode(panel_id: str, mode: str) -> bool:
    if mode not in TICKET_MODES:
        return False
    config = db.get_document("tickets_config") or {}
    panel = (config.get("panels") or {}).get(panel_id)
    if not panel:
        return False
    normalize_panel(panel)
    panel["ticket_mode"] = mode
    panel["purchase_settings"]["allow_without_purchase"] = mode == "mixed"
    panel["has_pending_changes"] = True
    db.save_document("tickets_config", config)
    return True
