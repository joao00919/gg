from __future__ import annotations

import re
from datetime import datetime, timezone

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.permission_matrix import has_capability
from .manager import ReferralManager


def _money(value: float) -> str:
    return f"R$ {float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _select_value(values: dict, key: str):
    value = values.get(key)
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


class ReferralConfigModal(disnake.ui.Modal):
    def __init__(self):
        cfg = ReferralManager.get_config()
        components = [
            disnake.ui.Label(
                text="Prefixo dos códigos",
                component=disnake.ui.TextInput(
                    custom_id="referral_prefix",
                    value=str(cfg.get("prefix", "ZYNEX")),
                    placeholder="ZYNEX",
                    required=True,
                    max_length=12,
                ),
                description="Exemplo gerado: ZYNEX-JOAO123.",
            ),
            disnake.ui.Label(
                text="Comissão em saldo interno (%)",
                component=disnake.ui.TextInput(
                    custom_id="referral_commission",
                    value=str(cfg.get("commission_percent", 5)),
                    placeholder="5",
                    required=True,
                    max_length=8,
                ),
            ),
            disnake.ui.Label(
                text="Desconto para o indicado (%)",
                component=disnake.ui.TextInput(
                    custom_id="referral_discount",
                    value=str(cfg.get("referred_discount_percent", 5)),
                    placeholder="5",
                    required=True,
                    max_length=8,
                ),
            ),
            disnake.ui.Label(
                text="Limite de usos por código",
                component=disnake.ui.TextInput(
                    custom_id="referral_max_uses",
                    value=str(cfg.get("max_uses_per_code", 100)),
                    placeholder="100",
                    required=True,
                    max_length=8,
                ),
            ),
            disnake.ui.Label(
                text="Compra mínima",
                component=disnake.ui.TextInput(
                    custom_id="referral_min_purchase",
                    value=str(cfg.get("minimum_purchase", 1)),
                    placeholder="1,00",
                    required=True,
                    max_length=16,
                ),
            ),
        ]
        super().__init__(
            title="Configurar programa de indicação",
            custom_id="Referral_ConfigModal",
            components=components,
        )

    async def callback(self, inter: disnake.ModalInteraction):
        if not has_capability(inter, "payments"):
            return await inter.response.send_message(
                f"{emoji.wrong} Você não possui permissão para alterar o programa de indicação.",
                ephemeral=True,
            )

        values = dict(getattr(inter, "text_values", {}) or {})
        values.update(getattr(inter, "resolved_values", {}) or {})
        prefix = str(_select_value(values, "referral_prefix") or "").strip().upper()
        prefix = re.sub(r"[^A-Z0-9-]", "", prefix)
        if not 2 <= len(prefix) <= 12:
            return await inter.response.send_message(
                f"{emoji.wrong} O prefixo deve ter entre 2 e 12 caracteres alfanuméricos.",
                ephemeral=True,
            )

        def number(key: str) -> float:
            raw = str(_select_value(values, key) or "0").strip().replace(" ", "")
            if "," in raw:
                raw = raw.replace(".", "").replace(",", ".")
            return float(raw)

        try:
            commission = number("referral_commission")
            discount = number("referral_discount")
            max_uses = int(number("referral_max_uses"))
            minimum = number("referral_min_purchase")
        except (TypeError, ValueError):
            return await inter.response.send_message(
                f"{emoji.wrong} Revise os valores numéricos informados.", ephemeral=True
            )

        if not 0 <= commission <= 100 or not 0 <= discount <= 100:
            return await inter.response.send_message(
                f"{emoji.wrong} Comissão e desconto devem ficar entre 0% e 100%.",
                ephemeral=True,
            )
        if not 1 <= max_uses <= 100000:
            return await inter.response.send_message(
                f"{emoji.wrong} O limite deve ficar entre 1 e 100.000 usos.",
                ephemeral=True,
            )
        if minimum < 0:
            return await inter.response.send_message(
                f"{emoji.wrong} A compra mínima não pode ser negativa.", ephemeral=True
            )

        ReferralManager.save_config({
            "prefix": prefix,
            "commission_percent": round(commission, 2),
            "referred_discount_percent": round(discount, 2),
            "max_uses_per_code": max_uses,
            "minimum_purchase": round(minimum, 2),
        })
        await inter.response.defer()
        await ReferralSystem.edit(inter)


class ReferralSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _text() -> str:
        cfg = ReferralManager.get_config()
        ranking = ReferralManager.ranking(5)
        ranking_text = "\n".join(
            f"`{i}.` <@{item.get('owner_id')}> — **{_money(item.get('total_commission', 0))}** — "
            f"`{item.get('approved_uses', 0)}` indicação(ões)"
            for i, item in enumerate(ranking, 1)
        ) or "Nenhuma comissão aprovada ainda."
        return (
            f"# {emoji.coin} Programa de indicação\n"
            "-# Painel > Loja > **Programa de Indicação**\n\n"
            f"{emoji.correct if cfg.get('enabled') else emoji.wrong} "
            f"**Status:** `{'Ativado' if cfg.get('enabled') else 'Desativado'}`\n"
            f"{emoji.unlock} **Formato:** `{cfg.get('prefix', 'ZYNEX')}-NOME123`\n"
            f"{emoji.coin} **Comissão:** `{cfg.get('commission_percent', 5)}% em saldo interno`\n"
            f"{emoji.cardbox} **Desconto do indicado:** `{cfg.get('referred_discount_percent', 5)}%`\n"
            f"{emoji.interrogation} **Compra mínima:** `{_money(cfg.get('minimum_purchase', 1))}`\n"
            f"{emoji.relations} **Limite por código:** `{cfg.get('max_uses_per_code', 100)} usos`\n\n"
            "-# A comissão só é aprovada após o pagamento confirmado, bloqueia autoindicação e é estornada em reembolsos.\n\n"
            "## Ranking de afiliados\n"
            f"{ranking_text}"
        )

    @classmethod
    def panel(cls, inter: disnake.Interaction) -> dict:
        cfg = ReferralManager.get_config()
        text = cls._text()
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        colors = db.get_document("custom_colors") or {}
        primary = colors.get("primary")
        buttons = disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Desativar" if cfg.get("enabled") else "Ativar",
                style=disnake.ButtonStyle.red if cfg.get("enabled") else disnake.ButtonStyle.green,
                emoji=emoji.wrong if cfg.get("enabled") else emoji.correct,
                custom_id="Referral_Toggle",
            ),
            disnake.ui.Button(
                label="Definir regras",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.settings2,
                custom_id="Referral_Configure",
            ),
            disnake.ui.Button(
                label="Histórico",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.receipt,
                custom_id="Referral_History",
            ),
        )
        back = disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Voltar",
                style=disnake.ButtonStyle.grey,
                emoji=emoji.back,
                custom_id="Loja_Panel",
            )
        )
        if mode == "embed":
            embed = disnake.Embed(description=text)
            if primary:
                embed.color = int(str(primary).replace("#", ""), 16)
            return {"embed": embed, "components": [buttons, back]}

        kwargs = {}
        if primary:
            kwargs["accent_colour"] = disnake.Colour(int(str(primary).replace("#", ""), 16))
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(text),
                    disnake.ui.Separator(),
                    buttons,
                    **kwargs,
                ),
                back,
            ]
        }

    @classmethod
    async def edit(cls, inter: disnake.Interaction) -> None:
        payload = cls.panel(inter)
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            await inter.edit_original_message(content=None, **payload)
        else:
            await inter.edit_original_message(
                **payload,
                flags=disnake.MessageFlags(is_components_v2=True),
            )

    @staticmethod
    def _history_text(limit: int = 20) -> str:
        data = db.get_document("referrals") or {}
        history = list(data.get("history") or [])[-limit:]
        if not history:
            return "Nenhuma movimentação de indicação registrada."
        labels = {
            "pending": "Pendente",
            "approved": "Aprovada",
            "reversed": "Estornada",
        }
        lines = []
        for item in reversed(history):
            event = str(item.get("type") or "evento")
            timestamp = int(item.get("timestamp") or 0)
            when = f"<t:{timestamp}:R>" if timestamp else "sem data"
            code = str(item.get("code") or "-")
            purchase = str(item.get("purchase_id") or item.get("cart_id") or "-")
            amount = float(item.get("commission") or 0)
            amount_text = f" — `{_money(amount)}`" if amount else ""
            lines.append(
                f"• **{labels.get(event, event.title())}** `{code}` — pedido `{purchase}`{amount_text} — {when}"
            )
        return "\n".join(lines)

    @commands.Cog.listener("on_button_click")
    async def buttons(self, inter: disnake.MessageInteraction):
        cid = inter.component.custom_id
        if cid not in {"Referral_Toggle", "Referral_Configure", "Referral_History"}:
            return
        if not has_capability(inter, "payments"):
            return await inter.response.send_message(
                f"{emoji.wrong} Você não possui permissão para gerenciar indicações.",
                ephemeral=True,
            )

        if cid == "Referral_Configure":
            return await inter.response.send_modal(ReferralConfigModal())
        if cid == "Referral_History":
            return await inter.response.send_message(
                f"{emoji.receipt} **Histórico de comissões**\n{self._history_text()}",
                ephemeral=True,
            )

        await inter.response.defer()
        cfg = ReferralManager.get_config()
        ReferralManager.save_config({"enabled": not cfg.get("enabled", True)})
        await self.edit(inter)


def setup(bot: commands.Bot):
    bot.add_cog(ReferralSystem(bot))
