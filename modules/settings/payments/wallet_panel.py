from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.permission_matrix import has_capability

TURBO_WITHDRAW_FEE = 1.50
from functions.payments.sync_wallet import (
    calculate_store_fee,
    create_sync_withdraw_from_settings,
    get_sync_balance_from_settings,
    global_wallet_is_configured,
)


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_number(data: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(data, dict):
        for key in keys:
            if key in data:
                try:
                    return float(data[key])
                except (TypeError, ValueError):
                    pass
        for value in data.values():
            found = _first_number(value, keys)
            if found is not None:
                return found
    return None



def _payment_entry() -> dict:
    config = db.get_document("payment_configs") or {}
    entry = config.get("sync_wallet") or {}
    if isinstance(entry, dict):
        return entry
    return {"enabled": bool(entry)}


def _save_entry(entry: dict) -> None:
    entry = dict(entry)
    entry.pop("api_key", None)
    config = db.get_document("payment_configs") or {}
    config["sync_wallet"] = entry
    db.save_document("payment_configs", config)
    pagamentos = db.get_document("pagamentos") or {}
    pagamentos["sync_wallet"] = bool(entry.get("enabled", False))
    db.save_document("pagamentos", pagamentos)


def _fee_text(percent: float, fixed: float) -> str:
    pct = f"{percent:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{pct}% + {_money(fixed)}"


def _store_fee_text(entry: dict) -> str:
    return _fee_text(
        _number(entry.get("store_fee_percent", 0.0)),
        _number(entry.get("store_fee_fixed", 0.0)),
    )


def _provider_fee_text(entry: dict) -> str:
    preview = calculate_store_fee(100.0, entry)
    return _fee_text(
        _number(preview.get("provider_percent", 0.60)),
        _number(preview.get("provider_fixed", 0.25)),
    )



class GlobalWalletWithdrawModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.Label(
                text="Chave Pix",
                component=disnake.ui.TextInput(
                    custom_id="wallet_withdraw_pix_key",
                    placeholder="Coloque uma Chave Pix",
                    required=True,
                    max_length=100,
                ),
            ),
            disnake.ui.Label(
                text="Valor do Saque",
                component=disnake.ui.TextInput(
                    custom_id="wallet_withdraw_amount",
                    placeholder="Informe o valor do saque em real!",
                    required=True,
                    max_length=20,
                ),
            ),
            disnake.ui.Label(
                text="Estilo de Saque",
                component=disnake.ui.StringSelect(
                    custom_id="wallet_withdraw_style",
                    placeholder="Retirada Turbo (R$ 1,50) - Imediata",
                    required=True,
                    min_values=1,
                    max_values=1,
                    options=[
                        disnake.SelectOption(
                            label="Retirada Turbo (R$ 1,50) - Imediata",
                            value="turbo",
                            description="Esse método é necessário ter ao menos R$ 1,50 extra.",
                        )
                    ],
                ),
            ),
        ]
        super().__init__(
            title="Realizar Saque",
            custom_id="GlobalWallet_WithdrawModal",
            components=components,
        )

    async def callback(self, inter: disnake.ModalInteraction):
        if not has_capability(inter, "withdrawals"):
            return await inter.response.send_message(
                f"{emoji.wrong} Você não possui permissão para solicitar saques.",
                ephemeral=True,
            )
        if not global_wallet_is_configured():
            return await inter.response.send_message(
                f"{emoji.wrong} A PurinCash ainda não está configurada.", ephemeral=True
            )

        values = dict(getattr(inter, "text_values", {}) or {})
        resolved = dict(getattr(inter, "resolved_values", {}) or {})
        withdraw_style = resolved.get("wallet_withdraw_style")
        if isinstance(withdraw_style, (list, tuple)):
            withdraw_style = withdraw_style[0] if withdraw_style else None
        if not withdraw_style:
            withdraw_style = values.get("wallet_withdraw_style")
        if withdraw_style != "turbo":
            return await inter.response.send_message(
                f"{emoji.wrong} Selecione um estilo de saque válido.", ephemeral=True
            )

        pix_key = str(values.get("wallet_withdraw_pix_key") or "").strip()
        if not pix_key:
            return await inter.response.send_message(
                f"{emoji.wrong} Informe uma Chave Pix válida.", ephemeral=True
            )

        raw_amount = str(values.get("wallet_withdraw_amount") or "").strip().replace("R$", "").replace(" ", "")
        if "," in raw_amount:
            raw_amount = raw_amount.replace(".", "").replace(",", ".")
        try:
            amount = round(float(raw_amount), 2)
        except (TypeError, ValueError):
            return await inter.response.send_message(
                f"{emoji.wrong} Informe um valor válido.", ephemeral=True
            )
        if amount < 5:
            return await inter.response.send_message(
                f"{emoji.wrong} O saque mínimo é de R$ 5,00.", ephemeral=True
            )

        # O modo Turbo exige saldo para o valor solicitado e a taxa fixa de R$ 1,50.
        try:
            balance_data = await get_sync_balance_from_settings()
            available = _first_number(
                balance_data,
                ("withdrawable", "withdrawableCents", "availableBalance", "available", "balance"),
            )
            if available is not None and "withdrawableCents" in balance_data:
                if available == _number(balance_data.get("withdrawableCents")):
                    available /= 100
            total_required = round(amount + TURBO_WITHDRAW_FEE, 2)
            if available is not None and total_required > float(available):
                return await inter.response.send_message(
                    f"{emoji.wrong} Saldo insuficiente para a Retirada Turbo.\n"
                    f"{emoji.coin} Necessário: `{_money(total_required)}`\n"
                    f"{emoji.wallet} Disponível: `{_money(available)}`",
                    ephemeral=True,
                )
        except Exception:
            # A API faz a validação definitiva caso a consulta de saldo falhe.
            pass

        await inter.response.defer(ephemeral=True)
        request_id = f"{getattr(inter, 'guild_id', 0)}:{getattr(inter, 'id', 0)}"
        requests = db.get_document("wallet_withdraw_requests") or {"items": {}}
        requests.setdefault("items", {})
        previous = requests["items"].get(request_id)
        if previous and previous.get("status") in {"processing", "completed"}:
            return await inter.followup.send(
                f"{emoji.interrogation} Esta solicitação já foi processada.", ephemeral=True
            )

        requests["items"][request_id] = {
            "status": "processing",
            "amount": amount,
            "requested_by": int(getattr(inter.author, "id", 0)),
            "withdraw_style": "turbo",
            "withdraw_style_label": "Retirada Turbo (R$ 1,50) - Imediata",
            "fee": TURBO_WITHDRAW_FEE,
            "total_required": round(amount + TURBO_WITHDRAW_FEE, 2),
            "created_at": int(datetime.now(timezone.utc).timestamp()),
        }
        db.save_document("wallet_withdraw_requests", requests)
        try:
            result = await create_sync_withdraw_from_settings(amount, pix_key)
            withdraw_id = str(result.get("id") or result.get("code") or "não informado")
            status = str(result.get("status") or "solicitado")
            requests["items"][request_id].update(
                {
                    "status": "completed",
                    "provider_status": status,
                    "withdraw_id": withdraw_id,
                    "completed_at": int(datetime.now(timezone.utc).timestamp()),
                }
            )
            db.save_document("wallet_withdraw_requests", requests)
            await inter.followup.send(
                f"{emoji.correct} Saque solicitado com sucesso.\n"
                f"{emoji.coin} Valor solicitado: `{_money(amount)}`\n"
                f"{emoji.receipt} Taxa Turbo: `{_money(TURBO_WITHDRAW_FEE)}`\n"
                f"{emoji.thunder} Estilo: `Retirada Turbo - Imediata`\n"
                f"{emoji.receipt} Identificador: `{withdraw_id}`\n"
                f"{emoji.interrogation} Status: `{status}`",
                ephemeral=True,
            )
        except Exception as exc:
            requests["items"][request_id].update(
                {"status": "failed", "failed_at": int(datetime.now(timezone.utc).timestamp())}
            )
            db.save_document("wallet_withdraw_requests", requests)
            await inter.followup.send(
                f"{emoji.wrong} Não foi possível solicitar o saque: {str(exc)[:300]}",
                ephemeral=True,
            )


class GlobalWalletPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def _balance() -> tuple[float | None, str | None]:
        if not global_wallet_is_configured():
            return None, None
        try:
            data = await get_sync_balance_from_settings()
            value = _first_number(
                data,
                ("withdrawable", "withdrawableCents", "availableBalance", "available", "balance"),
            )
            if value is not None and "withdrawableCents" in data and value == _number(data.get("withdrawableCents")):
                value /= 100
            return value, None
        except Exception as exc:
            return None, str(exc)[:180]

    @classmethod
    async def payload(cls, inter: disnake.Interaction, display_name: str = "Carteira Integrada", prefix: str = "GlobalWallet") -> dict:
        entry = _payment_entry()
        entry.setdefault("store_fee_percent", 0.0)
        entry.setdefault("store_fee_fixed", 0.0)
        enabled = bool(entry.get("enabled", False))
        responsibility = str(entry.get("fee_responsibility") or "").lower()
        if responsibility not in {"store", "client"}:
            responsibility = "store" if bool(entry.get("cover_fee", False)) else "client"
        configured = global_wallet_is_configured()
        balance, balance_error = await cls._balance()
        balance_text = _money(balance) if balance is not None else "Indisponível"
        active = enabled and configured

        status_emoji = emoji.on if active else emoji.off
        status_text = "Ativado" if active else "Desativado"
        responsibility_text = "Loja" if responsibility == "store" else "Cliente"
        text = (
            f"# {emoji.z0}\n"
            f"-# Painel > Configurações > Formas de Pagamento > {display_name}\n\n"
            f"**{display_name}**\n"
            f"• Status: `{status_text}`\n"
            f"• Saldo Disponível: `{balance_text}`\n"
            f"• Responsabilidade Taxa: `{responsibility_text}`\n\n"
            "*Taxas de Operação:*\n"
            f"> Entrada: `{_provider_fee_text(entry)}`"
        )
        if balance_error and configured:
            text += "\n\n-# Não foi possível atualizar o saldo agora; tente novamente."

        row1 = disnake.ui.ActionRow(
            disnake.ui.Button(
                label=f"Desligar {display_name}" if enabled else f"Ativar {display_name}",
                style=disnake.ButtonStyle.red if enabled else disnake.ButtonStyle.green,
                emoji=emoji.off if enabled else emoji.on,
                custom_id=f"{prefix}_Toggle",
                disabled=not configured,
            ),
            disnake.ui.Button(label="Saque", style=disnake.ButtonStyle.grey, emoji=emoji.bank, custom_id=f"{prefix}_Withdraw", disabled=not active),
            disnake.ui.Button(label="Responsabilidade Taxa", style=disnake.ButtonStyle.grey, emoji=emoji.config, custom_id=f"{prefix}_FeeResponsibility"),
        )
        row2 = disnake.ui.ActionRow(
            disnake.ui.Button(label="Exibir Extrato", style=disnake.ButtonStyle.grey, emoji=emoji.config, custom_id=f"{prefix}_Statement")
        )
        back = disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"{prefix}_Back")
        )

        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        colors = db.get_document("custom_colors") or {}
        primary = colors.get("primary")
        if mode == "embed":
            embed = disnake.Embed(description=text)
            if primary:
                embed.color = int(str(primary).replace("#", ""), 16)
            return {"embed": embed, "components": [row1, row2, back]}

        kwargs = {}
        if primary:
            kwargs["accent_colour"] = disnake.Colour(int(str(primary).replace("#", ""), 16))
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(text), disnake.ui.Separator(), row1, row2, **kwargs
                ),
                back,
            ]
        }

    @classmethod
    async def edit(cls, inter: disnake.MessageInteraction, display_name: str = "Carteira Integrada", prefix: str = "GlobalWallet") -> None:
        payload = await cls.payload(inter, display_name=display_name, prefix=prefix)
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            await inter.edit_original_message(content=None, **payload)
        else:
            await inter.edit_original_message(
                **payload, flags=disnake.MessageFlags(is_components_v2=True)
            )

    @commands.Cog.listener("on_button_click")
    async def buttons(self, inter: disnake.MessageInteraction):
        cid = inter.component.custom_id
        if not cid.startswith("GlobalWallet_"):
            return
        prefix = "GlobalWallet"
        display_name = "Carteira Integrada"
        action = cid.split("_", 1)[1]

        if action == "Back":
            if not has_capability(inter, "payments"):
                return await inter.response.send_message(
                    f"{emoji.wrong} Você não possui permissão para gerenciar pagamentos.", ephemeral=True
                )
            await inter.response.defer()
            from .cog import ConfigurarPagamentos

            mode = (db.get_document("custom_mode") or {}).get("mode", "components")
            if mode == "embed":
                embed, components = ConfigurarPagamentos.pagamentos_embed(inter, "pix")
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await inter.edit_original_message(
                    components=ConfigurarPagamentos.pagamentos_components(inter, "pix"),
                    flags=disnake.MessageFlags(is_components_v2=True),
                )
            return

        if action == "Withdraw":
            if not has_capability(inter, "withdrawals"):
                return await inter.response.send_message(
                    f"{emoji.wrong} Você não possui permissão para solicitar saques.", ephemeral=True
                )
            return await inter.response.send_modal(GlobalWalletWithdrawModal())


        if not has_capability(inter, "payments"):
            return await inter.response.send_message(
                f"{emoji.wrong} Você não possui permissão para gerenciar pagamentos.", ephemeral=True
            )

        if action == "Toggle":
            if not global_wallet_is_configured():
                return await inter.response.send_message(
                    f"{emoji.wrong} A Carteira Integrada não está disponível. Use o PIX Manual ou outro provedor configurado.", ephemeral=True
                )
            await inter.response.defer()
            entry = _payment_entry()
            entry["enabled"] = not bool(entry.get("enabled", False))
            _save_entry(entry)
            await self.edit(inter, display_name=display_name, prefix=prefix)
            return

        if action == "FeeResponsibility":
            await inter.response.defer()
            entry = _payment_entry()
            current = str(entry.get("fee_responsibility") or "").lower()
            if current not in {"store", "client"}:
                current = "store" if bool(entry.get("cover_fee", False)) else "client"
            new_value = "client" if current == "store" else "store"
            entry["fee_responsibility"] = new_value
            entry["cover_fee"] = new_value == "store"
            _save_entry(entry)
            await self.edit(inter, display_name=display_name, prefix=prefix)
            return

        if action == "Statement":
            if not has_capability(inter, "payments"):
                return await inter.response.send_message(
                    f"{emoji.wrong} Você não possui permissão para visualizar o extrato.", ephemeral=True
                )
            requests = db.get_document("wallet_withdraw_requests") or {"items": {}}
            items = list((requests.get("items") or {}).values())[-10:]
            if not items:
                return await inter.response.send_message(
                    f"{emoji.wallet} Nenhuma movimentação de saque foi registrada ainda.", ephemeral=True
                )
            lines = []
            for item in reversed(items):
                amount = item.get("amount") or item.get("net_amount") or 0
                status = item.get("status") or "pendente"
                lines.append(f"• `{_money(_number(amount) or 0)}` — `{status}`")
            return await inter.response.send_message(
                f"{emoji.wallet} **Extrato recente**\n" + "\n".join(lines), ephemeral=True
            )

        if action == "Refresh":
            await inter.response.defer()
            await self.edit(inter, display_name=display_name, prefix=prefix)
            return



def setup(bot: commands.Bot):
    bot.add_cog(GlobalWalletPanel(bot))
