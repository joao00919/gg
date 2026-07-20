from __future__ import annotations

import disnake
from disnake.ext import commands

from functions.automation_rules import merge_rules
from functions.database import database as db
from functions.emoji import emoji
from functions.message import embed_message, message
from functions.perms import perms
from functions.permission_matrix import has_capability


class BusinessRulesModal(disnake.ui.Modal):
    def __init__(self):
        rules = merge_rules(db.get_document("automation_rules") or {})
        super().__init__(
            title="Automação por regras",
            custom_id="BusinessRules_Modal",
            components=[
                disnake.ui.Label(
                    text="Estoque baixo",
                    description="Avisar quando o estoque total ficar abaixo deste valor.",
                    component=disnake.ui.TextInput(
                        custom_id="stock_threshold",
                        value=str(rules["stock"].get("threshold", 5)),
                        max_length=3,
                        required=True,
                    ),
                ),
                disnake.ui.Label(
                    text="Ticket sem resposta",
                    description="Tempo em minutos antes do alerta e aumento de prioridade.",
                    component=disnake.ui.TextInput(
                        custom_id="stale_minutes",
                        value=str(rules["tickets"].get("stale_minutes", 30)),
                        max_length=4,
                        required=True,
                    ),
                ),
                disnake.ui.Label(
                    text="Pontos por real",
                    description="Pontos adicionados depois do pagamento confirmado.",
                    component=disnake.ui.TextInput(
                        custom_id="points_per_real",
                        value=str(rules["payment"].get("points_per_real", 1)),
                        max_length=6,
                        required=True,
                    ),
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        if not all(has_capability(inter, capability) for capability in ("stock", "payments", "tickets")):
            return await inter.response.send_message(
                f"{emoji.wrong} Apenas Owner ou Admin pode alterar todas as regras de uma vez.",
                ephemeral=True,
            )
        try:
            threshold = int(inter.text_values.get("stock_threshold", "5"))
            stale = int(inter.text_values.get("stale_minutes", "30"))
            points = float(inter.text_values.get("points_per_real", "1").replace(",", "."))
        except (TypeError, ValueError):
            return await inter.response.send_message("Informe somente valores numéricos válidos.", ephemeral=True)
        if not 1 <= threshold <= 999:
            return await inter.response.send_message("O limite de estoque deve ficar entre 1 e 999.", ephemeral=True)
        if not 1 <= stale <= 1440:
            return await inter.response.send_message("O tempo do ticket deve ficar entre 1 e 1440 minutos.", ephemeral=True)
        if not 0 <= points <= 1000:
            return await inter.response.send_message("Os pontos por real devem ficar entre 0 e 1000.", ephemeral=True)
        rules = merge_rules(db.get_document("automation_rules") or {})
        rules["stock"]["threshold"] = threshold
        rules["tickets"]["stale_minutes"] = stale
        rules["payment"]["points_per_real"] = points
        db.save_document("automation_rules", rules)
        await inter.response.send_message(
            f"Regras atualizadas: estoque abaixo de {threshold}, ticket parado por {stale} minutos e {points:g} ponto(s) por real.",
            ephemeral=True,
        )


class BusinessRulesConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _text() -> str:
        rules = merge_rules(db.get_document("automation_rules") or {})
        stock, payment, tickets = rules["stock"], rules["payment"], rules["tickets"]
        return (
            "# Automação por regras\n"
            "-# Painel > Automações > Regras da Loja\n\n"
            f"{emoji.cardbox} **Estoque abaixo de {stock.get('threshold', 5)}:** "
            f"`{'Ativo' if stock.get('enabled', True) else 'Desativado'}`\n"
            "Avisar administrador, marcar estoque baixo e desativar promoção.\n\n"
            f"{emoji.pix} **Pagamento aprovado:** "
            f"`{'Ativo' if payment.get('deliver_product', True) else 'Desativado'}`\n"
            "Entregar produto, adicionar pontos, atualizar VIP, enviar comprovante e liberar avaliação.\n\n"
            f"{emoji.verified} **Ticket parado por {tickets.get('stale_minutes', 30)} minutos:** "
            f"`{'Ativo' if tickets.get('enabled', True) else 'Desativado'}`\n"
            "Mencionar suporte e aumentar a prioridade automaticamente."
        )

    @classmethod
    def panel_components(cls):
        colors = db.get_document("custom_colors") or {}
        kwargs = {}
        if colors.get("primary"):
            kwargs["accent_colour"] = disnake.Colour(int(colors["primary"].replace("#", ""), 16))
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(cls._text()),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Estoque", emoji=emoji.cardbox, custom_id="BusinessRules_Toggle_stock"),
                    disnake.ui.Button(label="Pagamento", emoji=emoji.pix, custom_id="BusinessRules_Toggle_payment"),
                    disnake.ui.Button(label="Tickets", emoji=emoji.verified, custom_id="BusinessRules_Toggle_tickets"),
                    disnake.ui.Button(label="Definir regras", emoji=emoji.settings2, custom_id="BusinessRules_Configure"),
                ),
                **kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarAutomações")
            ),
        ]

    @classmethod
    def panel_embed(cls):
        colors = db.get_document("custom_colors") or {}
        kwargs = {"color": int(colors["primary"].replace("#", ""), 16)} if colors.get("primary") else {}
        embed = disnake.Embed(title="Automação por regras", description=cls._text().replace("# Automação por regras\n", ""), **kwargs)
        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Estoque", emoji=emoji.cardbox, custom_id="BusinessRules_Toggle_stock"),
                disnake.ui.Button(label="Pagamento", emoji=emoji.pix, custom_id="BusinessRules_Toggle_payment"),
                disnake.ui.Button(label="Tickets", emoji=emoji.verified, custom_id="BusinessRules_Toggle_tickets"),
                disnake.ui.Button(label="Definir regras", emoji=emoji.settings2, custom_id="BusinessRules_Configure"),
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id="VoltarAutomações")),
        ]
        return embed, components

    @commands.Cog.listener("on_button_click")
    async def on_button(self, inter: disnake.MessageInteraction):
        cid = inter.component.custom_id
        if cid == "BusinessRules_Configure":
            if not all(has_capability(inter, capability) for capability in ("stock", "payments", "tickets")):
                return await inter.response.send_message(
                    f"{emoji.wrong} Apenas Owner ou Admin pode alterar todas as regras de uma vez.",
                    ephemeral=True,
                )
            return await inter.response.send_modal(BusinessRulesModal())
        if not cid.startswith("BusinessRules_Toggle_"):
            return
        section = cid.rsplit("_", 1)[-1]
        capability = {"stock": "stock", "payment": "payments", "tickets": "tickets"}.get(section)
        if not capability or not has_capability(inter, capability):
            return await inter.response.send_message(
                f"{emoji.wrong} Você não possui permissão para alterar esta regra.",
                ephemeral=True,
            )
        rules = merge_rules(db.get_document("automation_rules") or {})
        if section == "stock":
            rules["stock"]["enabled"] = not rules["stock"].get("enabled", True)
        elif section == "payment":
            enabled = not rules["payment"].get("deliver_product", True)
            for key in ("deliver_product", "add_points", "update_vip", "send_receipt", "enable_review"):
                rules["payment"][key] = enabled
        elif section == "tickets":
            rules["tickets"]["enabled"] = not rules["tickets"].get("enabled", True)
        else:
            return
        db.save_document("automation_rules", rules)
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            embed, components = self.panel_embed()
            await inter.response.edit_message(embed=embed, components=components)
        else:
            await inter.response.edit_message(components=self.panel_components())


def setup(bot):
    bot.add_cog(BusinessRulesConfigCog(bot))
