from __future__ import annotations

import copy
import time
from typing import Any

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.interaction_runtime import respond_error, respond_panel
from .status import sales_enabled, toggle_sales


def _e(name: str, fallback: str = "config"):
    return getattr(emoji, name, getattr(emoji, fallback, None))


def _accent_kwargs() -> dict[str, Any]:
    colors = db.get_document("custom_colors") or {}
    primary = colors.get("primary")
    if primary:
        try:
            return {"accent_colour": disnake.Colour(int(str(primary).replace("#", ""), 16))}
        except Exception:
            pass
    return {}


def _store_options() -> list[disnake.SelectOption]:
    """Opções na mesma ordem da interface de referência."""
    return [
        disnake.SelectOption(
            label="Gerenciar Produtos",
            value="produtos",
            emoji=_e("cardbox"),
            description="Crie, Configure e Edite seus produtos.",
        ),
        disnake.SelectOption(
            label="Personalizar Loja",
            value="personalizar",
            emoji=_e("wand", "edit"),
            description="Personalize sua loja com criatividade.",
        ),
        disnake.SelectOption(
            label="Preferências",
            value="preferencias",
            emoji=_e("settings", "config"),
            description="Configure preferências do seu sistema de loja.",
        ),
        disnake.SelectOption(
            label="Extensões",
            value="extensoes",
            emoji=_e("commands", "config"),
            description="Adicione extensões ao seu sistema de loja.",
        ),
        disnake.SelectOption(
            label="Sistema de Saldo",
            value="saldo",
            emoji=_e("wallet"),
            description="Configure o sistema de saldo para sua loja.",
        ),
        disnake.SelectOption(
            label="Cashback",
            value="cashback",
            emoji=_e("bank"),
            description="Configure o sistema de cashback para sua loja.",
        ),
        disnake.SelectOption(
            label="Programa de Indicação",
            value="afiliados",
            emoji=_e("dollar"),
            description="Comissões, descontos, ranking e histórico.",
        ),
    ]


def _snapshot_store_config() -> dict[str, Any]:
    docs = (
        "custom_colors",
        "custom_mode",
        "loja_preferences",
        "loja_personalization",
        "loja_doubt_button",
        "loja_status",
        "loja_saldo_config",
        "loja_cashback_config",
        "loja_referral_config",
    )
    return {name: copy.deepcopy(db.get_document(name) or {}) for name in docs}


def _apply_store_snapshot(snapshot: dict[str, Any]) -> None:
    for name, value in snapshot.items():
        if isinstance(name, str) and isinstance(value, dict):
            db.save_document(name, copy.deepcopy(value))


class SaveStoreTemplateModal(disnake.ui.Modal):
    def __init__(self):
        super().__init__(
            title="Salvar template da loja",
            custom_id="Loja_Template_Save_Modal",
            components=[
                disnake.ui.TextInput(
                    label="Nome do template",
                    placeholder="Ex.: Configuração principal",
                    custom_id="template_name",
                    min_length=1,
                    max_length=80,
                    required=True,
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        name = str(inter.text_values.get("template_name") or "").strip()
        if not name:
            return await inter.response.send_message(
                f"{_e('wrong')} Informe um nome válido.", ephemeral=True
            )
        templates = db.get_document("loja_templates") or {}
        template_id = str(int(time.time() * 1000))
        templates[template_id] = {
            "id": template_id,
            "name": name,
            "created_by": str(getattr(inter.user, "id", "")),
            "created_at": int(time.time()),
            "snapshot": _snapshot_store_config(),
        }
        db.save_document("loja_templates", templates)
        await respond_panel(inter, Loja.templates_panel(inter), prefer_edit=True)


class Loja(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def panel(self, inter: disnake.Interaction) -> dict:
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        return self._panel_embed(inter) if mode == "embed" else self._panel_components(inter)

    def _panel_components(self, inter: disnake.Interaction) -> dict:
        enabled = sales_enabled()
        toggle_label = "Desligar Vendas" if enabled else "Ligar Vendas"
        toggle_style = disnake.ButtonStyle.danger if enabled else disnake.ButtonStyle.success
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {_e('zenyx2')}\n-# Painel > **Loja**"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        "Configure a sua loja selecionando uma seção abaixo.\n"
                        "Para configurar as formas de pagamento, acesse as configurações."
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.ActionRow(
                        disnake.ui.StringSelect(
                            custom_id="Loja_Select",
                            placeholder="Selecione uma seção para configurar",
                            options=_store_options(),
                        )
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label=toggle_label,
                            style=toggle_style,
                            emoji=_e("power"),
                            custom_id="Loja_ToggleSales",
                        ),
                        disnake.ui.Button(
                            label="Templates",
                            style=disnake.ButtonStyle.secondary,
                            emoji=_e("save"),
                            custom_id="Loja_Templates",
                        ),
                    ),
                    **_accent_kwargs(),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Voltar",
                        style=disnake.ButtonStyle.secondary,
                        emoji=_e("back"),
                        custom_id="PainelInicial",
                    )
                ),
            ]
        }

    def _panel_embed(self, inter: disnake.Interaction) -> dict:
        enabled = sales_enabled()
        colors = db.get_document("custom_colors") or {}
        embed = disnake.Embed(
            title=f"{_e('zenyx2')} Configurar Loja",
            description=(
                "-# Painel > **Loja**\n\n"
                "Configure a sua loja selecionando uma seção abaixo.\n"
                "Para configurar as formas de pagamento, acesse as configurações."
            ),
        )
        primary = colors.get("primary")
        if primary:
            try:
                embed.color = int(str(primary).replace("#", ""), 16)
            except Exception:
                pass
        return {
            "embed": embed,
            "components": [
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="Loja_Select",
                        placeholder="Selecione uma seção para configurar",
                        options=_store_options(),
                    )
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Desligar Vendas" if enabled else "Ligar Vendas",
                        style=disnake.ButtonStyle.danger if enabled else disnake.ButtonStyle.success,
                        emoji=_e("power"),
                        custom_id="Loja_ToggleSales",
                    ),
                    disnake.ui.Button(
                        label="Templates",
                        style=disnake.ButtonStyle.secondary,
                        emoji=_e("save"),
                        custom_id="Loja_Templates",
                    ),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Voltar",
                        style=disnake.ButtonStyle.secondary,
                        emoji=_e("back"),
                        custom_id="PainelInicial",
                    )
                ),
            ],
        }

    @staticmethod
    def templates_panel(inter: disnake.Interaction) -> dict:
        templates = db.get_document("loja_templates") or {}
        options = []
        for template_id, data in sorted(
            templates.items(), key=lambda item: int((item[1] or {}).get("created_at", 0)), reverse=True
        )[:25]:
            options.append(
                disnake.SelectOption(
                    label=str((data or {}).get("name") or "Template")[:100],
                    value=str(template_id),
                    description="Aplicar este template à configuração da loja",
                    emoji=_e("save"),
                )
            )
        select = disnake.ui.StringSelect(
            custom_id="Loja_Templates_Select",
            placeholder=(
                f"[{len(templates)}] Selecione um template"
                if options
                else "Nenhum template salvo"
            ),
            options=options or [
                disnake.SelectOption(label="Nenhum template salvo", value="none")
            ],
            disabled=not bool(options),
        )
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(
                        f"# {_e('zenyx2')}\n-# Painel > Loja > **Templates**"
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        "Salve a configuração visual e operacional atual da loja ou aplique um template já salvo.\n"
                        "-# Produtos, estoques, vendas e credenciais não são alterados."
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.ActionRow(select),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Salvar Configuração Atual",
                            style=disnake.ButtonStyle.success,
                            emoji=_e("save"),
                            custom_id="Loja_Template_Save",
                        ),
                        disnake.ui.Button(
                            label="Restaurar Padrão",
                            style=disnake.ButtonStyle.secondary,
                            emoji=_e("reload"),
                            custom_id="Loja_Template_Default",
                        ),
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

    async def display_store_panel(self, inter: disnake.Interaction):
        return await respond_panel(inter, self.panel(inter), prefer_edit=True)

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid == "Loja_Panel":
            return await self.display_store_panel(inter)
        if cid == "Loja_ToggleSales":
            toggle_sales(
                updated_by=getattr(inter.user, "id", None),
                updated_at=int(time.time()),
            )
            return await respond_panel(inter, self.panel(inter), prefer_edit=True)
        if cid == "Loja_Templates":
            return await respond_panel(inter, self.templates_panel(inter), prefer_edit=True)
        if cid == "Loja_Template_Save":
            return await inter.response.send_modal(SaveStoreTemplateModal())
        if cid == "Loja_Template_Default":
            db.save_document("loja_status", {"enabled": True, "updated_by": None, "updated_at": int(time.time())})
            db.save_document("loja_preferences", {})
            db.save_document("loja_personalization", {})
            await inter.response.send_message(
                f"{_e('correct')} Configuração padrão restaurada.", ephemeral=True
            )
            return

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid == "Loja_Templates_Select":
            template_id = str(inter.values[0]) if inter.values else ""
            template = (db.get_document("loja_templates") or {}).get(template_id)
            if not template:
                return await inter.response.send_message(
                    f"{_e('wrong')} Template não encontrado.", ephemeral=True
                )
            _apply_store_snapshot(template.get("snapshot") or {})
            await inter.response.send_message(
                f"{_e('correct')} Template **{template.get('name', 'Template')}** aplicado.",
                ephemeral=True,
            )
            return

        if cid != "Loja_Select":
            return

        choice = str(inter.values[0]) if inter.values else ""
        try:
            if choice == "produtos":
                from .products.cog import GerenciarProdutos
                panel_data = GerenciarProdutos(self.bot).panel(inter)
            elif choice == "personalizar":
                from .personalization.cog import PersonalizarLoja
                panel_data = PersonalizarLoja.panel(inter)
            elif choice == "preferencias":
                from .preferences.cog import PreferenciasLoja
                panel_data = PreferenciasLoja.panel(inter)
            elif choice == "extensoes":
                from modules.settings.extensions.cog import ExtensionsPanel
                panel_data = ExtensionsPanel(self.bot).panel_payload(inter, back_custom_id="Painel_Loja")
            elif choice == "saldo":
                from .saldo.cog import SaldoSystem
                panel_data = SaldoSystem(self.bot).panel(inter)
            elif choice == "cashback":
                from .cashback.cog import CashbackSystem
                panel_data = CashbackSystem(self.bot).panel(inter)
            elif choice == "afiliados":
                from .referrals.cog import ReferralSystem
                panel_data = ReferralSystem(self.bot).panel(inter)
            else:
                panel_data = self.panel(inter)
            return await respond_panel(inter, panel_data, prefer_edit=True)
        except Exception as exc:
            return await respond_error(inter, f"Não foi possível abrir esta seção: {str(exc)[:180]}")


def setup(bot: commands.Bot):
    bot.add_cog(Loja(bot))
