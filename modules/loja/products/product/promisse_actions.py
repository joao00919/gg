from __future__ import annotations

import time
from typing import Any

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
from functions.loja_products import parse_price_brl_to_float
from functions.utils import utils

from .campos.fields.configurar import (
    ConfigurarCampo,
    build_advanced_panel,
    build_config_extra_panel,
)


def _values(inter: disnake.ModalInteraction) -> dict[str, Any]:
    data = {}
    data.update(getattr(inter, "text_values", {}) or {})
    data.update(getattr(inter, "resolved_values", {}) or {})
    return data


def _load(product_id: str, field_id: str) -> tuple[dict, dict, dict]:
    products = db.get_document("loja_products") or {}
    product = products.get(product_id, {}) or {}
    field = (product.get("campos") or {}).get(field_id, {}) or {}
    return products, product, field


def _save(products: dict, product_id: str, product: dict, field_id: str | None = None, field: dict | None = None) -> None:
    if field_id is not None and field is not None:
        product.setdefault("campos", {})[field_id] = field
    products[product_id] = product
    db.save_document("loja_products", products)


async def _wait_and_edit(inter: disnake.MessageInteraction | disnake.ModalInteraction, panel: dict) -> None:
    mode = (db.get_document("custom_mode") or {}).get("mode", "components")
    if not inter.response.is_done():
        await (embed_message if mode == "embed" else message).wait(inter, send=False)
    if mode == "embed":
        await inter.edit_original_message(content=None, **panel)
    else:
        await inter.edit_original_message(**panel)


async def _sync(inter, product_id: str) -> None:
    try:
        from modules.loja.products.product.edit import sync_product_messages_silently
        await sync_product_messages_silently(inter.client, product_id)
    except Exception as exc:
        print(f"[PROMISSE] Falha ao sincronizar {product_id}: {exc}")


class PromisseEditProductModal(disnake.ui.Modal):
    def __init__(self, product_id: str, field_id: str):
        self.product_id = product_id
        self.field_id = field_id
        _products, product, field = _load(product_id, field_id)
        description = str(field.get("description") or "Não configurado ainda...")
        components = [
            disnake.ui.Label(
                text="Nome do Produto",
                component=disnake.ui.TextInput(
                    custom_id="name",
                    value=str(field.get("name") or product.get("name") or "")[:100],
                    required=True,
                    max_length=100,
                ),
            ),
            disnake.ui.Label(
                text="Valor do Produto",
                component=disnake.ui.TextInput(
                    custom_id="price",
                    value=(str(field.get("price") or "") if float(field.get("price") or 0) else None),
                    placeholder="Digite o valor do produto (número)",
                    required=True,
                    max_length=20,
                ),
            ),
            disnake.ui.Label(
                text="Descrição do Produto (Opcional)",
                component=disnake.ui.TextInput(
                    custom_id="description",
                    value=description[:1000],
                    style=disnake.TextInputStyle.paragraph,
                    required=False,
                    max_length=1000,
                ),
            ),
        ]
        super().__init__(
            title="Alterar Informações do Produto",
            components=components,
            custom_id=f"promisse_edit:{product_id}:{field_id}",
        )

    async def callback(self, inter: disnake.ModalInteraction):
        values = _values(inter)
        name = str(values.get("name") or "").strip()
        raw_price = str(values.get("price") or "").strip()
        description = str(values.get("description") or "").strip()
        try:
            price = parse_price_brl_to_float(raw_price)
        except Exception:
            return await inter.response.send_message(
                f"{emoji.wrong} Digite um valor válido. Exemplo: `19,90`.", ephemeral=True
            )
        products, product, field = _load(self.product_id, self.field_id)
        if not product or not field:
            return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
        now = int(time.time())
        field["name"] = name
        field["price"] = max(0.0, float(price))
        field["description"] = None if description in {"", "Não configurado ainda..."} else description
        field["updated_at"] = now
        product["name"] = name
        product.setdefault("info", {})["updated_at"] = now
        _save(products, self.product_id, product, self.field_id, field)
        await _sync(inter, self.product_id)
        await _wait_and_edit(inter, ConfigurarCampo.panel(inter, self.product_id, self.field_id))


class PromisseValuesModal(disnake.ui.Modal):
    def __init__(self, product_id: str, field_id: str):
        self.product_id = product_id
        self.field_id = field_id
        _products, _product, field = _load(product_id, field_id)
        cond = field.get("condicoes") or {}
        components = []
        labels = [
            ("Valor mínimo", "valorMin"),
            ("Valor máximo", "valorMax"),
            ("Quantidade mínima", "quantidadeMin"),
            ("Quantidade máxima", "quantidadeMax"),
        ]
        for label, key in labels:
            value = cond.get(key)
            components.append(
                disnake.ui.Label(
                    text=label,
                    component=disnake.ui.TextInput(
                        custom_id=key,
                        value=str(value) if value not in (None, "") else None,
                        placeholder="Deixe vazio para não limitar",
                        required=False,
                        max_length=20,
                    ),
                )
            )
        super().__init__(
            title="Editar Condições do Produto",
            components=components,
            custom_id=f"promisse_values:{product_id}:{field_id}",
        )

    async def callback(self, inter: disnake.ModalInteraction):
        values = _values(inter)
        products, product, field = _load(self.product_id, self.field_id)
        if not product or not field:
            return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
        cond = field.setdefault("condicoes", {})
        for key in ("valorMin", "valorMax"):
            raw = str(values.get(key) or "").strip()
            if not raw:
                cond[key] = None
            else:
                try:
                    cond[key] = parse_price_brl_to_float(raw)
                except Exception:
                    return await inter.response.send_message(
                        f"{emoji.wrong} O campo **{key}** contém um valor inválido.", ephemeral=True
                    )
        for key in ("quantidadeMin", "quantidadeMax"):
            raw = str(values.get(key) or "").strip()
            if not raw:
                cond[key] = None
            elif raw.isdigit() and int(raw) >= 1:
                cond[key] = int(raw)
            else:
                return await inter.response.send_message(
                    f"{emoji.wrong} As quantidades precisam ser números inteiros maiores que zero.", ephemeral=True
                )
        field["updated_at"] = int(time.time())
        _save(products, self.product_id, product, self.field_id, field)
        await _sync(inter, self.product_id)
        await _wait_and_edit(inter, build_config_extra_panel(inter, self.product_id, self.field_id))


class PromisseTextSettingModal(disnake.ui.Modal):
    def __init__(self, product_id: str, field_id: str, key: str, title: str, label: str, placeholder: str):
        self.product_id = product_id
        self.field_id = field_id
        self.key = key
        _products, product, _field = _load(product_id, field_id)
        current = (product.get("info") or {}).get(key)
        component = disnake.ui.TextInput(
            custom_id="value",
            value=str(current)[:500] if current else None,
            placeholder=placeholder,
            required=False,
            max_length=500,
        )
        super().__init__(
            title=title,
            components=[disnake.ui.Label(text=label, component=component)],
            custom_id=f"promisse_setting:{key}:{product_id}:{field_id}",
        )

    async def callback(self, inter: disnake.ModalInteraction):
        value = str(_values(inter).get("value") or "").strip()
        products, product, field = _load(self.product_id, self.field_id)
        if not product:
            return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
        if self.key in {"banner", "thumbnail"} and value and not utils.is_valid_url(value):
            return await inter.response.send_message(f"{emoji.wrong} Informe uma URL válida começando com `https://`.", ephemeral=True)
        if self.key == "hex_color":
            value = utils.normalize_hex_color(value) if value else "#ADD8E6"
            if not value:
                return await inter.response.send_message(f"{emoji.wrong} Informe uma cor HEX válida. Exemplo: `#ADD8E6`.", ephemeral=True)
        product.setdefault("info", {})[self.key] = value or None
        product["info"]["updated_at"] = int(time.time())
        _save(products, self.product_id, product, self.field_id, field)
        await _sync(inter, self.product_id)
        await _wait_and_edit(inter, build_advanced_panel(inter, self.product_id, self.field_id))


class PromisseActions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(inter.component, "custom_id", "") or "")
        known = (
            "Promisse_EditarProduto:", "Promisse_ToggleEntrega:", "Promisse_ConfigExtra:",
            "Promisse_Configuracoes:", "Promisse_Sincronizar:", "Promisse_Deletar:",
            "Promisse_ConfirmarDeletar:", "Promisse_CancelarDeletar:", "Promisse_VoltarProduto:",
            "Promisse_EditarValores:", "Promisse_ResetarCargos:", "Promisse_Banner:",
            "Promisse_Miniatura:", "Promisse_CargoObrigatorio:", "Promisse_CorEmbed:",
            "Promisse_Categoria:", "Promisse_ToggleCupons:", "Promisse_RemoverCargoObrigatorio:",
            "Promisse_EstoqueFantasma:",
        )
        if not custom_id.startswith(known):
            return
        try:
            prefix, product_id, field_id = custom_id.split(":", 2)
        except ValueError:
            return

        products, product, field = _load(product_id, field_id)
        if prefix not in {"Promisse_ConfirmarDeletar"} and (not product or not field):
            return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)

        if prefix == "Promisse_EditarProduto":
            return await inter.response.send_modal(PromisseEditProductModal(product_id, field_id))

        if prefix == "Promisse_EstoqueFantasma":
            current = str(field.get("stock_style") or "traditional").lower()
            field["stock_style"] = "ghost" if current != "ghost" else "traditional"
            field["updated_at"] = int(time.time())
            _save(products, product_id, product, field_id, field)
            from .campos.fields.estoque.visualizar import panel as stock_panel
            await _wait_and_edit(inter, stock_panel(inter, product_id, field_id))
            return await inter.followup.send(
                f"{emoji.correct} Estilo de estoque alterado para **{'Fantasma' if field['stock_style'] == 'ghost' else 'Tradicional'}**.",
                ephemeral=True,
            )

        if prefix == "Promisse_ToggleEntrega":
            current = str((product.get("info") or {}).get("delivery_type") or "automatic")
            new_value = "manual" if current != "manual" else "automatic"
            product.setdefault("info", {})["delivery_type"] = new_value
            product["info"]["updated_at"] = int(time.time())
            _save(products, product_id, product, field_id, field)
            await _sync(inter, product_id)
            await _wait_and_edit(inter, ConfigurarCampo.panel(inter, product_id, field_id))
            await inter.followup.send(
                f"{emoji.correct} O estilo de entrega foi alterado para `{'manual' if new_value == 'manual' else 'automático'}`.",
                ephemeral=True,
            )
            return

        if prefix == "Promisse_ConfigExtra":
            return await _wait_and_edit(inter, build_config_extra_panel(inter, product_id, field_id))

        if prefix == "Promisse_Configuracoes":
            return await _wait_and_edit(inter, build_advanced_panel(inter, product_id, field_id))

        if prefix == "Promisse_VoltarProduto" or prefix == "Promisse_CancelarDeletar":
            return await _wait_and_edit(inter, ConfigurarCampo.panel(inter, product_id, field_id))

        if prefix == "Promisse_Sincronizar":
            await _sync(inter, product_id)
            await _wait_and_edit(inter, ConfigurarCampo.panel(inter, product_id, field_id))
            return await inter.followup.send(f"{emoji.correct} Produto sincronizado com sucesso!", ephemeral=True)

        if prefix == "Promisse_Deletar":
            panel = {
                "components": [
                    disnake.ui.Container(
                        disnake.ui.TextDisplay(
                            f"# {emoji.warn} Deletar produto\n"
                            f"Você tem certeza que deseja deletar **{field.get('name') or product.get('name')}**?\n"
                            "Esta ação remove o produto, estoque e mensagens vinculadas."
                        ),
                        disnake.ui.Separator(),
                        disnake.ui.ActionRow(
                            disnake.ui.Button(label="Deletar", emoji=emoji.delete, style=disnake.ButtonStyle.danger, custom_id=f"Promisse_ConfirmarDeletar:{product_id}:{field_id}"),
                            disnake.ui.Button(label="Cancelar", emoji=emoji.back, custom_id=f"Promisse_CancelarDeletar:{product_id}:{field_id}"),
                        ),
                    )
                ]
            }
            return await _wait_and_edit(inter, panel)

        if prefix == "Promisse_ConfirmarDeletar":
            products.pop(product_id, None)
            db.save_document("loja_products", products)
            if not inter.response.is_done():
                await inter.response.defer()
            return await inter.edit_original_message(
                content=f"{emoji.correct} O produto foi deletado com sucesso!",
                embed=None,
                components=[],
            )

        if prefix == "Promisse_EditarValores":
            return await inter.response.send_modal(PromisseValuesModal(product_id, field_id))

        if prefix == "Promisse_ResetarCargos":
            field.setdefault("cargos", {})["authorized"] = []
            _save(products, product_id, product, field_id, field)
            await _wait_and_edit(inter, build_config_extra_panel(inter, product_id, field_id))
            return await inter.followup.send(f"{emoji.correct} Cargos autorizados foram resetados.", ephemeral=True)

        if prefix == "Promisse_Banner":
            return await inter.response.send_modal(PromisseTextSettingModal(product_id, field_id, "banner", "Configurar Banner", "URL do Banner", "https://..."))
        if prefix == "Promisse_Miniatura":
            return await inter.response.send_modal(PromisseTextSettingModal(product_id, field_id, "thumbnail", "Configurar Miniatura", "URL da Miniatura", "https://..."))
        if prefix == "Promisse_CorEmbed":
            return await inter.response.send_modal(PromisseTextSettingModal(product_id, field_id, "hex_color", "Configurar Cor Embed", "Cor em HEX", "#ADD8E6"))
        if prefix == "Promisse_Categoria":
            return await inter.response.send_modal(PromisseTextSettingModal(product_id, field_id, "category_name", "Configurar Categoria", "Nome da Categoria", "Ex.: Assinaturas"))

        if prefix == "Promisse_ToggleCupons":
            info = product.setdefault("info", {})
            info["coupons_enabled"] = not bool(info.get("coupons_enabled", True))
            _save(products, product_id, product, field_id, field)
            return await _wait_and_edit(inter, build_advanced_panel(inter, product_id, field_id))

        if prefix == "Promisse_CargoObrigatorio":
            return await inter.response.send_message(
                content="Selecione o cargo obrigatório para comprar este produto.",
                components=[
                    disnake.ui.ActionRow(
                        disnake.ui.RoleSelect(
                            placeholder="Selecione um cargo",
                            custom_id=f"Promisse_CargoObrigatorioSelect:{product_id}:{field_id}",
                            min_values=1,
                            max_values=1,
                        )
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(label="Remover Cargo", emoji=emoji.delete, style=disnake.ButtonStyle.danger, custom_id=f"Promisse_RemoverCargoObrigatorio:{product_id}:{field_id}")
                    ),
                ],
                ephemeral=True,
            )

        if prefix == "Promisse_RemoverCargoObrigatorio":
            product.setdefault("info", {})["required_role_id"] = None
            _save(products, product_id, product, field_id, field)
            return await inter.response.send_message(f"{emoji.correct} Cargo obrigatório removido.", ephemeral=True)

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(inter.component, "custom_id", "") or "")
        if custom_id.startswith("Promisse_CargosAutorizados:"):
            _, product_id, field_id = custom_id.split(":", 2)
            products, product, field = _load(product_id, field_id)
            role_ids = [int(value) for value in (inter.values or []) if str(value).isdigit()]
            field.setdefault("cargos", {})["authorized"] = role_ids
            _save(products, product_id, product, field_id, field)
            await _wait_and_edit(inter, build_config_extra_panel(inter, product_id, field_id))
            return
        if custom_id.startswith("Promisse_CargoObrigatorioSelect:"):
            _, product_id, field_id = custom_id.split(":", 2)
            products, product, field = _load(product_id, field_id)
            selected = next((int(value) for value in (inter.values or []) if str(value).isdigit()), None)
            product.setdefault("info", {})["required_role_id"] = selected
            _save(products, product_id, product, field_id, field)
            return await inter.response.send_message(f"{emoji.correct} Cargo obrigatório configurado.", ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(PromisseActions(bot))
