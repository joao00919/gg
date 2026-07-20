from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import disnake

from functions.database import database as db
from functions.emoji import emoji
from modules.loja.cart.purchase_manager import PurchaseManager

TICKET_MODES = {
    "common": "Ticket comum",
    "purchase": "Vinculado à compra",
    "mixed": "Misto",
    "warranty": "Garantia",
    "financial": "Financeiro",
}

DEFAULT_PURCHASE_SETTINGS = {
    "max_purchases": 25,
    "warranty_days": 30,
    "allow_without_purchase": False,
    "show_delivery_items": True,
}


def _purchase_manager():
    """Obtém a classe atual, inclusive após hot-reload de extensões."""
    import sys

    module = sys.modules.get(__name__)
    return getattr(module, "PurchaseManager", PurchaseManager)


def normalize_panel(panel: dict) -> dict:
    panel.setdefault("ticket_mode", "common")
    panel.setdefault("purchase_settings", {})
    panel["purchase_settings"] = {
        **DEFAULT_PURCHASE_SETTINGS,
        **(panel.get("purchase_settings") or {}),
    }
    if panel.get("ticket_mode") == "mixed":
        panel["purchase_settings"]["allow_without_purchase"] = True
    return panel


def mode_requires_purchase(panel: dict) -> bool:
    mode = normalize_panel(panel).get("ticket_mode")
    return mode in {"purchase", "mixed", "warranty"}


def money(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def date_text(timestamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%d/%m/%Y")
    except (TypeError, ValueError, OSError):
        return "Data não informada"


def order_reference(purchase: dict) -> str:
    purchase_id = str(purchase.get("purchase_id") or "SEM-ID")
    return purchase_id if purchase_id.upper().startswith("ORDE_") else f"ORDE_{purchase_id}"


def warranty_info(purchase: dict, warranty_days: int) -> tuple[bool, Optional[int]]:
    try:
        bought_at = int(purchase.get("timestamp") or 0)
    except (TypeError, ValueError):
        return False, None
    if bought_at <= 0:
        return False, None
    now = int(datetime.now(timezone.utc).timestamp())
    expires = bought_at + max(0, int(warranty_days)) * 86400
    return now <= expires, expires


def get_user_purchases(user_id: int, panel: dict) -> list[dict]:
    panel = normalize_panel(panel)
    settings = panel["purchase_settings"]
    limit = max(1, min(int(settings.get("max_purchases") or 25), 25))
    purchases = _purchase_manager().get_user_purchases(user_id, limit=limit)
    if panel.get("ticket_mode") != "warranty":
        return purchases
    warranty_days = int(settings.get("warranty_days") or 30)
    return [purchase for purchase in purchases if warranty_info(purchase, warranty_days)[0]]


def find_purchase(user_id: int, purchase_id: str) -> Optional[dict]:
    for purchase in _purchase_manager().get_user_purchases(user_id, limit=None):
        if str(purchase.get("purchase_id")) == str(purchase_id):
            return purchase
    return None


def iter_open_tickets() -> list[tuple[str, str, dict]]:
    data = db.get_document("tickets_data") or {}
    found: list[tuple[str, str, dict]] = []
    for panel_id, users in (data.get("panels") or {}).items():
        for user_id, tickets in (users or {}).items():
            for ticket in tickets or []:
                if ticket.get("status") == "open":
                    found.append((str(panel_id), str(user_id), ticket))
    return found


def active_ticket_for_purchase(guild: disnake.Guild, user_id: int, purchase_id: str) -> Optional[disnake.abc.GuildChannel]:
    for _panel_id, stored_user_id, ticket in iter_open_tickets():
        if stored_user_id != str(user_id):
            continue
        if str(ticket.get("purchase_id") or "") != str(purchase_id):
            continue
        channel_id = ticket.get("ticket_id")
        if not channel_id:
            continue
        channel = guild.get_channel(int(channel_id)) or guild.get_thread(int(channel_id))
        if channel:
            return channel
    return None


def context_from_purchase(panel: dict, purchase: Optional[dict], *, no_purchase: bool = False) -> dict:
    panel = normalize_panel(panel)
    context = {
        "ticket_mode": panel.get("ticket_mode", "common"),
        "priority": "normal",
        "purchase_found": False,
        "purchase_id": None,
        "purchase": None,
        "no_purchase": bool(no_purchase),
    }
    if purchase:
        snapshot = {
            "purchase_id": purchase.get("purchase_id"),
            "timestamp": purchase.get("timestamp"),
            "product": dict(purchase.get("product") or {}),
            "field": dict(purchase.get("field") or {}),
            "quantity": purchase.get("quantity", 1),
            "pricing": dict(purchase.get("pricing") or {}),
            "payment": dict(purchase.get("payment") or {}),
            "delivery": dict(purchase.get("delivery") or {}),
            "metadata": dict(purchase.get("metadata") or {}),
        }
        context["purchase_id"] = str(purchase.get("purchase_id") or "")
        context["purchase"] = snapshot
        context["purchase_found"] = True
        context["priority"] = "high"
    return context


def selector_payload(user_id: int, panel_id: str, panel: dict, option_id: str | None = None) -> dict:
    panel = normalize_panel(panel)
    purchases = get_user_purchases(user_id, panel)
    options: list[disnake.SelectOption] = []

    if panel.get("ticket_mode") == "mixed":
        options.append(
            disnake.SelectOption(
                label="Abrir ticket sem vincular compra",
                value="__without_purchase__",
                description="Atendimento geral sem pedido específico",
                emoji=emoji.interrogation,
            )
        )

    warranty_days = int(panel["purchase_settings"].get("warranty_days") or 30)
    for purchase in purchases:
        product = str((purchase.get("product") or {}).get("name") or "Produto")
        field = str((purchase.get("field") or {}).get("name") or "")
        quantity = int(purchase.get("quantity") or 1)
        value = (purchase.get("pricing") or {}).get("final_price", 0)
        detail = " - ".join(part for part in (product, field) if part and part.lower() != "pagamento")
        suffix = ""
        if panel.get("ticket_mode") == "warranty":
            valid, expires = warranty_info(purchase, warranty_days)
            suffix = f" - Garantia até {date_text(expires)}" if valid and expires else ""
        description = (
            f"{detail} - {money(value)} - {quantity}x - {date_text(purchase.get('timestamp'))}{suffix}"
        )[:100]
        options.append(
            disnake.SelectOption(
                label=f"Compra {order_reference(purchase)}"[:100],
                value=str(purchase.get("purchase_id"))[:100],
                description=description,
                emoji=emoji.relations,
            )
        )

    if not options:
        title = "Nenhuma compra elegível"
        description = (
            "Não encontramos compras dentro da garantia para este atendimento."
            if panel.get("ticket_mode") == "warranty"
            else "Não encontramos compras no seu histórico para este painel."
        )
        return {
            "content": f"{emoji.interrogation} **{title}**\n{description}",
            "components": [],
        }

    embed = disnake.Embed(
        title="Compras encontradas",
        description=(
            f"{emoji.correct} Encontramos **{len(purchases)}** compra(s) disponível(is).\n"
            "Selecione abaixo qual compra deseja usar neste atendimento."
        ),
        color=disnake.Color.from_rgb(28, 29, 32),
    )
    select = disnake.ui.StringSelect(
        custom_id=f"ticket_purchase_select:{panel_id}:{option_id or '-'}",
        placeholder="Selecione uma compra",
        min_values=1,
        max_values=1,
        options=options[:25],
    )
    return {"embed": embed, "components": [disnake.ui.ActionRow(select)]}


def purchase_summary(
    context: dict,
    panel: dict,
    *,
    queue_position: int,
    created_at: int,
    queue_total: int | None = None,
    assigned_to: int | None = None,
) -> str:
    mode = context.get("ticket_mode", "common")
    purchase = context.get("purchase") or {}
    priority_key = str(context.get("priority") or ("high" if purchase else "normal")).lower()
    priority_labels = {
        "critical": "Crítica",
        "high": "Alta",
        "normal": "Normal",
        "low": "Baixa",
    }
    priority_label = priority_labels.get(priority_key, "Normal")
    purchase_found = bool(purchase or context.get("purchase_found") or context.get("purchase_id"))
    queue_label = (
        "Em atendimento"
        if assigned_to
        else f"#{max(1, int(queue_position or 1))}" + (f" de {queue_total}" if queue_total else "")
    )

    lines = [f"# {emoji.online} Atendimento Online", ""]
    lines.append(f"{emoji.interrogation} **Tipo:** `{TICKET_MODES.get(mode, mode)}`")
    lines.append(f"{emoji.search} **Prioridade:** `{priority_label}`")
    lines.append(f"{emoji.relations} **Posição na fila:** `{queue_label}`")
    lines.append(f"{emoji.calendar} **Aberto:** <t:{created_at}:R>")
    lines.append(
        f"{emoji.verified} **Atendente responsável:** "
        + (f"<@{assigned_to}>" if assigned_to else "`Não assumido`")
    )
    lines.append(
        f"{emoji.correct if purchase_found else emoji.interrogation} **Compra encontrada:** "
        f"`{'Sim — atendimento prioritário' if purchase_found else 'Não — atendimento geral'}`"
    )

    if purchase:
        product = purchase.get("product") or {}
        field = purchase.get("field") or {}
        pricing = purchase.get("pricing") or {}
        delivery = purchase.get("delivery") or {}
        metadata = purchase.get("metadata") or {}
        lines.extend([
            "",
            "## Informações da compra",
            f"{emoji.unlock} **Pedido:** `{order_reference(purchase)}`",
            f"{emoji.cardbox} **Produto/Sistema:** `{product.get('name') or 'Não informado'}`",
            f"{emoji.cardbox} **Variação/Plano:** `{field.get('name') or 'Padrão'}`",
            f"{emoji.coin} **Valor:** `{money(pricing.get('final_price'))}`",
            f"{emoji.calendar} **Data:** `{date_text(purchase.get('timestamp'))}`",
            "",
            "## Informações da entrega",
            f"{emoji.back} **Tipo:** `{metadata.get('delivery_type') or 'Não informado'}`",
            f"{emoji.correct} **Itens entregues:** `{delivery.get('items_count', len(delivery.get('items') or []))}`",
        ])
        warranty_days = int(normalize_panel(panel)["purchase_settings"].get("warranty_days") or 30)
        valid, expires = warranty_info(purchase, warranty_days)
        lines.extend([
            "",
            "## Informações da garantia",
            f"{emoji.correct if valid else emoji.wrong} **Status:** `{'Ativa' if valid else 'Expirada'}`",
            f"{emoji.calendar} **Validade:** `{date_text(expires) if expires else 'Não informada'}`",
        ])
    else:
        lines.extend(["", f"{emoji.interrogation} Este ticket não está vinculado a uma compra."])

    return "\n".join(lines)
