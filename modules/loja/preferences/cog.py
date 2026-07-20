"""Preferências da loja organizadas no formato da interface de referência."""
from __future__ import annotations

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.interaction_runtime import respond_error, respond_panel


def _e(name: str, fallback: str = "config"):
    return getattr(emoji, name, getattr(emoji, fallback, None))


def _accent_kwargs() -> dict:
    colors = db.get_document("custom_colors") or {}
    primary = colors.get("primary")
    if primary:
        try:
            return {"accent_colour": disnake.Colour(int(str(primary).replace("#", ""), 16))}
        except Exception:
            pass
    return {}


def _reviews_enabled() -> bool:
    return bool((db.get_document("loja_reviews_config") or {}).get("enabled", True))


class PreferenciasLoja(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _options() -> list[disnake.SelectOption]:
        prefs = db.get_document("loja_preferences") or {}
        cart_style = str(prefs.get("cart_style") or "channel")
        style_label = "Canal" if cart_style == "channel" else "Tópico Privado"
        review_action = "Desligar Avaliação" if _reviews_enabled() else "Ligar Avaliação"
        review_desc = (
            "Sistema de avaliação esta Ligado"
            if _reviews_enabled()
            else "Sistema de avaliação esta Desligado"
        )
        return [
            disnake.SelectOption(
                label="Alterar Estilo Carrinho",
                value="cart_style",
                emoji=_e("cart"),
                description=f"Configure o estilo do carrinho de compras, atualmente: {style_label}",
            ),
            disnake.SelectOption(
                label="Botão Dúvidas",
                value="doubt_button",
                emoji=_e("link", "speech"),
                description="Configure o botão de dúvidas",
            ),
            disnake.SelectOption(
                label="Termos de Compra",
                value="terms",
                emoji=_e("termos", "textc"),
                description="Configure os termos de compra",
            ),
            disnake.SelectOption(
                label="Gerenciar BlackList",
                value="blacklist",
                emoji=_e("lock"),
                description="Gerencie usuários bloqueados",
            ),
            disnake.SelectOption(
                label="Sistema solicitar estoque",
                value="stock_requests",
                emoji=_e("cardbox"),
                description="Edite e publique o painel de solicitação de estoque",
            ),
            disnake.SelectOption(
                label="Sistema de Rank de Vendas",
                value="sales_rank",
                emoji=_e("fire"),
                description="Edite e publique o painel de Rank de Vendas",
            ),
            disnake.SelectOption(
                label=review_action,
                value="reviews_toggle",
                emoji=_e("like", "star"),
                description=review_desc,
            ),
        ]

    @staticmethod
    def panel(inter: disnake.Interaction) -> dict:
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            embed = disnake.Embed(
                title="Preferências da Loja",
                description="-# Painel > Loja > **Preferências**\n\nGerencie as preferências globais da sua loja.",
            )
            return {
                "embed": embed,
                "components": [
                    disnake.ui.ActionRow(
                        disnake.ui.StringSelect(
                            custom_id="Loja_Preferencias_Select",
                            placeholder="Selecione uma configuração",
                            options=PreferenciasLoja._options(),
                        )
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(label="Voltar", emoji=_e("back"), custom_id="Painel_Loja")
                    ),
                ],
            }
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {_e('zenyx2')}\n-# Painel > Loja > **Preferências**"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay("Gerencie as preferências globais da sua loja."),
                    disnake.ui.Separator(),
                    disnake.ui.ActionRow(
                        disnake.ui.StringSelect(
                            custom_id="Loja_Preferencias_Select",
                            placeholder="Selecione uma configuração",
                            options=PreferenciasLoja._options(),
                        )
                    ),
                    **_accent_kwargs(),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Voltar",
                        style=disnake.ButtonStyle.secondary,
                        emoji=_e("back"),
                        custom_id="Painel_Loja",
                    )
                ),
            ]
        }

    @staticmethod
    def cart_style_panel(inter: disnake.Interaction) -> dict:
        prefs = db.get_document("loja_preferences") or {}
        current = str(prefs.get("cart_style") or "channel")
        current_text = "Canal" if current == "channel" else "Tópico Privado"
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(
                        f"# {_e('zenyx2')}\n-# Painel > Loja > Preferências > **Estilo do Carrinho**"
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        f"**Estilo atual:** `{current_text}`\n"
                        "Escolha como o carrinho será organizado para o cliente."
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Canal",
                            style=disnake.ButtonStyle.success if current == "channel" else disnake.ButtonStyle.secondary,
                            emoji=_e("textc"),
                            custom_id="Loja_CartStyle:channel",
                            disabled=current == "channel",
                        ),
                        disnake.ui.Button(
                            label="Tópico Privado",
                            style=disnake.ButtonStyle.success if current == "thread" else disnake.ButtonStyle.secondary,
                            emoji=_e("lock"),
                            custom_id="Loja_CartStyle:thread",
                            disabled=current == "thread",
                        ),
                    ),
                    **_accent_kwargs(),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Voltar", emoji=_e("back"), custom_id="Loja_Preferencias")
                ),
            ]
        }

    @staticmethod
    def rank_panel(inter: disnake.Interaction) -> dict:
        prefs = db.get_document("loja_preferences") or {}
        enabled = bool(prefs.get("sales_rank_enabled", True))
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(
                        f"# {_e('zenyx2')}\n-# Painel > Loja > Preferências > **Rank de Vendas**"
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        f"**Status:** `{'Ligado' if enabled else 'Desligado'}`\n"
                        "O ranking utiliza as vendas aprovadas registradas pelo bot."
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Desligar Rank" if enabled else "Ligar Rank",
                            style=disnake.ButtonStyle.danger if enabled else disnake.ButtonStyle.success,
                            emoji=_e("fire"),
                            custom_id="Loja_RankToggle",
                        )
                    ),
                    **_accent_kwargs(),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Voltar", emoji=_e("back"), custom_id="Loja_Preferencias")
                ),
            ]
        }

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid == "Loja_Preferencias":
            return await respond_panel(inter, self.panel(inter), prefer_edit=True)
        if cid.startswith("Loja_CartStyle:"):
            value = cid.split(":", 1)[1]
            if value not in {"channel", "thread"}:
                return await inter.response.send_message(f"{_e('wrong')} Estilo inválido.", ephemeral=True)
            prefs = db.get_document("loja_preferences") or {}
            prefs["cart_style"] = value
            db.save_document("loja_preferences", prefs)
            return await respond_panel(inter, self.cart_style_panel(inter), prefer_edit=True)
        if cid == "Loja_RankToggle":
            prefs = db.get_document("loja_preferences") or {}
            prefs["sales_rank_enabled"] = not bool(prefs.get("sales_rank_enabled", True))
            db.save_document("loja_preferences", prefs)
            return await respond_panel(inter, self.rank_panel(inter), prefer_edit=True)

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        if str(inter.component.custom_id or "") != "Loja_Preferencias_Select":
            return
        value = str(inter.values[0]) if inter.values else ""
        try:
            if value == "cart_style":
                panel = self.cart_style_panel(inter)
            elif value == "doubt_button":
                from ..personalization.doubt_button import DoubtButtonSystem
                panel = DoubtButtonSystem.panel_doubt_button(inter, back_custom_id="Loja_Preferencias")
            elif value == "terms":
                from .terms import TermsPreferences
                panel = TermsPreferences.panel(inter)
            elif value == "blacklist":
                from modules.settings.bloquear.cog import ConfigurarBlacklist
                panel = ConfigurarBlacklist.panel(inter, back_custom_id="Loja_Preferencias")
            elif value == "stock_requests":
                from .solicitar_estoque import StockRequestPreferences
                panel = StockRequestPreferences.panel(inter)
            elif value == "sales_rank":
                panel = self.rank_panel(inter)
            elif value == "reviews_toggle":
                db.save_document("loja_reviews_config", {"enabled": not _reviews_enabled()})
                panel = self.panel(inter)
            else:
                panel = self.panel(inter)
            return await respond_panel(inter, panel, prefer_edit=True)
        except Exception as exc:
            return await respond_error(inter, f"Erro ao carregar preferência: {str(exc)[:180]}")


def setup(bot: commands.Bot):
    bot.add_cog(PreferenciasLoja(bot))
