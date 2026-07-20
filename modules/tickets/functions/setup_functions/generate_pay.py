from __future__ import annotations

import time
import uuid
from typing import Any, Optional

import disnake

from functions.database import database as db
from functions.emoji import emoji
from functions.payments.sync_wallet import (
    create_sync_payment_from_settings,
    global_wallet_is_configured,
)
from ..permissions import check_attendant_permissions
from ...queue import find_ticket_record


def _find_first(data: Any, keys: tuple[str, ...]) -> Optional[Any]:
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if value not in (None, "", [], {}):
                return value
        for value in data.values():
            found = _find_first(value, keys)
            if found not in (None, "", [], {}):
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_first(value, keys)
            if found not in (None, "", [], {}):
                return found
    return None


def _parse_brl(raw: str) -> float:
    text = str(raw or "").strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    value = round(float(text), 2)
    if value <= 0:
        raise ValueError("O valor deve ser maior que zero.")
    return value


def _money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class TicketPaymentModal(disnake.ui.Modal):
    def __init__(self, bot, owner_id: int, ticket_id: int):
        self.bot = bot
        self.owner_id = int(owner_id)
        self.ticket_id = int(ticket_id)
        super().__init__(
            title="Gerar pagamento do ticket",
            components=[
                disnake.ui.TextInput(
                    label="Valor da cobrança",
                    placeholder="Ex.: 49,90",
                    custom_id="amount",
                    max_length=20,
                ),
                disnake.ui.TextInput(
                    label="Descrição",
                    placeholder="Ex.: Renovação do plano Premium",
                    custom_id="description",
                    max_length=180,
                    required=False,
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        try:
            amount = _parse_brl(inter.text_values.get("amount", ""))
        except (TypeError, ValueError):
            return await inter.followup.send(
                f"{emoji.wrong} Informe um valor válido, como `49,90`.", ephemeral=True
            )

        if not global_wallet_is_configured():
            return await inter.followup.send(
                f"{emoji.wrong} A Carteira Integrada está indisponível no momento. Selecione o PIX Manual ou outro método ativo.",
                ephemeral=True,
            )

        description = (inter.text_values.get("description") or "").strip()
        if not description:
            description = f"Cobrança do ticket {inter.channel.name}"

        owner = inter.guild.get_member(self.owner_id)
        if owner is None:
            try:
                owner = await self.bot.fetch_user(self.owner_id)
            except Exception:
                owner = None

        try:
            result = await create_sync_payment_from_settings(
                amount,
                description=description,
                customer_name=getattr(owner, "display_name", None) or getattr(owner, "name", None),
                customer_external_id=str(self.owner_id),
                metadata={
                    "source": "ticket_payment",
                    "guildId": str(inter.guild_id or ""),
                    "channelId": str(inter.channel_id or ""),
                    "ticketId": str(self.ticket_id),
                    "buyerId": str(self.owner_id),
                    "createdBy": str(inter.author.id),
                },
            )
        except Exception as exc:
            return await inter.followup.send(
                f"{emoji.wrong} Não foi possível gerar o pagamento: {str(exc)[:500]}",
                ephemeral=True,
            )

        checkout_url = _find_first(result, (
            "checkout_url", "url", "init_point", "invoice_url", "payment_url",
            "hosted_url", "ticket_url", "link", "redirect_url",
        ))
        copy_code = _find_first(result, (
            "copy_paste", "pix_copia_cola", "brCode", "emv", "code",
            "qr_code_text", "qrcode_text", "qrCode",
        ))
        payment_id = _find_first(result, ("payment_id", "paymentId", "id", "invoice_id"))
        if not copy_code and not checkout_url:
            return await inter.followup.send(
                f"{emoji.wrong} O provedor não retornou um código PIX nem um link de pagamento.",
                ephemeral=True,
            )

        token = uuid.uuid4().hex[:16]
        payments = db.get_document("ticket_payments") or {"items": {}}
        payments.setdefault("items", {})[token] = {
            "token": token,
            "payment_id": str(payment_id or ""),
            "ticket_id": self.ticket_id,
            "channel_id": inter.channel_id,
            "guild_id": inter.guild_id,
            "user_id": self.owner_id,
            "created_by": inter.author.id,
            "created_at": int(time.time()),
            "amount": amount,
            "description": description,
            "status": "pending",
            "checkout_url": str(checkout_url or ""),
            "copy_code": str(copy_code or ""),
        }
        db.save_document("ticket_payments", payments)

        embed = disnake.Embed(
            title=f"{emoji.online} Pagamento do atendimento",
            description=(
                f"Cobrança criada para <@{self.owner_id}>.\n"
                f"**Descrição:** {description}\n"
                f"**Valor:** `{_money(amount)}`\n"
                f"**Status:** `Aguardando pagamento`"
            ),
            color=disnake.Color.from_rgb(25, 26, 29),
        )
        if copy_code:
            safe_code = str(copy_code)
            embed.add_field(
                name="PIX copia e cola",
                value=f"```{safe_code[:990]}```",
                inline=False,
            )
        embed.set_footer(text=f"Cobrança gerada por {inter.author.display_name}")

        buttons = []
        if copy_code:
            buttons.append(disnake.ui.Button(
                label="Copiar código PIX",
                emoji=emoji.pix,
                style=disnake.ButtonStyle.grey,
                custom_id=f"ticket_payment_copy:{token}",
            ))
        if checkout_url and str(checkout_url).startswith(("http://", "https://")):
            buttons.append(disnake.ui.Button(
                label="Abrir pagamento",
                emoji=emoji.wallet,
                style=disnake.ButtonStyle.link,
                url=str(checkout_url),
            ))

        await inter.channel.send(
            content=f"<@{self.owner_id}>",
            embed=embed,
            components=[disnake.ui.ActionRow(*buttons)] if buttons else None,
            allowed_mentions=disnake.AllowedMentions(users=True, roles=False, everyone=False),
        )
        await inter.followup.send(
            f"{emoji.correct} Pagamento de `{_money(amount)}` criado com sucesso.",
            ephemeral=True,
        )


async def generate_pay(inter: disnake.MessageInteraction, bot):
    if not await check_attendant_permissions(inter.author, inter.channel.id):
        return await inter.response.send_message(
            f"{emoji.wrong} Você não tem permissão para gerar pagamentos neste ticket.",
            ephemeral=True,
        )

    _panel_id, owner_id, ticket, _tickets_data = find_ticket_record(inter.channel.id)
    if not ticket or ticket.get("status") != "open" or not owner_id:
        return await inter.response.send_message(
            f"{emoji.wrong} Não foi possível localizar o cliente deste ticket.",
            ephemeral=True,
        )
    await inter.response.send_modal(TicketPaymentModal(bot, int(owner_id), inter.channel.id))


async def copy_ticket_payment(inter: disnake.MessageInteraction, token: str):
    payments = db.get_document("ticket_payments") or {}
    record = (payments.get("items") or {}).get(str(token))
    if not record or not record.get("copy_code"):
        return await inter.response.send_message(
            f"{emoji.wrong} Este código PIX não está mais disponível.", ephemeral=True
        )
    code = str(record["copy_code"])
    if len(code) > 1900:
        code = code[:1900]
    await inter.response.send_message(
        f"{emoji.pix} **PIX copia e cola**\n```{code}```",
        ephemeral=True,
    )
