from __future__ import annotations

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.utils import utils
from functions.text_utils import safe_textdisplay
from modules.loja.cart.stock_manager import StockManager


def _get_stock_display(product_id: str, field_id: str) -> str:
    products = db.get_document("loja_products") or {}
    product = products.get(product_id, {}) or {}
    field = (product.get("campos") or {}).get(field_id, {}) or {}
    if (field.get("infinite_stock") or {}).get("enabled"):
        return "Infinito"
    return str(StockManager.get_available_stock(product_id, field_id) or 0)


def _product_and_field(product_id: str, field_id: str) -> tuple[dict, dict]:
    products = db.get_document("loja_products") or {}
    product = products.get(product_id, {}) or {}
    field = (product.get("campos") or {}).get(field_id, {}) or {}
    return product, field


def _colour_kwargs(product: dict, *, embed: bool = False) -> dict:
    info = product.get("info") or {}
    colors = db.get_document("custom_colors") or {}
    raw = str(info.get("hex_color") or colors.get("primary") or "#ADD8E6").replace("#", "")
    try:
        value = int(raw, 16)
    except (TypeError, ValueError):
        value = 0xADD8E6
    return {"color" if embed else "accent_colour": value if embed else disnake.Colour(value)}


def _value_or_dash(value) -> str:
    if value is None or str(value).strip() == "":
        return "-"
    return str(value)


def _authorized_roles_text(field: dict, guild: disnake.Guild | None = None) -> str:
    cargos = field.get("cargos") or {}
    role_ids = cargos.get("authorized") or cargos.get("permitidos") or []
    role_ids = [int(role_id) for role_id in role_ids if str(role_id).isdigit()]
    if not role_ids:
        return "Todos Cargos"
    if guild:
        names = []
        for role_id in role_ids[:10]:
            role = guild.get_role(role_id)
            names.append(role.name if role else str(role_id))
        return ", ".join(names)
    return f"{len(role_ids)} cargo(s)"


def _main_text(product_id: str, field_id: str, guild: disnake.Guild | None = None) -> tuple[str, str, str]:
    product, field = _product_and_field(product_id, field_id)
    info = product.get("info") or {}
    product_name = safe_textdisplay(field.get("name") or product.get("name") or product_id, 80)
    price = utils.format_price_brl(float(field.get("price") or 0.0))
    stock = _get_stock_display(product_id, field_id)
    stock_text = stock if stock == "Infinito" else f"{stock} Unidades"
    delivery = "Manual" if info.get("delivery_type") == "manual" else "Automático"
    description = str(field.get("description") or "").strip() or "Não configurado ainda..."
    description = safe_textdisplay(description, 1200)
    cond = field.get("condicoes") or {}
    roles = _authorized_roles_text(field, guild)

    header = f"# {emoji.zenyx2}\n-# Painel > Loja > Produtos > {product_name}"
    body = (
        "**Informações do Produto**\n"
        f"-# Nome: `{product_name}` | Preço: `{price}`\n"
        f"-# Estoque: `{stock_text}` | Estilo da Entrega: `{delivery}`\n"
        "-# Descrição:\n"
        f"```\n{description}\n```"
    )
    conditions = (
        "**Condições atuais**\n"
        f"-# Valor mínimo: `{_value_or_dash(cond.get('valorMin'))}`\n"
        f"-# Valor máximo: `{_value_or_dash(cond.get('valorMax'))}`\n"
        f"-# Quantidade mínima: `{_value_or_dash(cond.get('quantidadeMin'))}`\n"
        f"-# Quantidade máxima: `{_value_or_dash(cond.get('quantidadeMax'))}`\n"
        f"-# Cargos autorizados a comprar: `{roles}`"
    )
    return header, body, conditions


def build_config_extra_panel(inter, product_id: str, field_id: str) -> dict:
    product, field = _product_and_field(product_id, field_id)
    name = safe_textdisplay(field.get("name") or product.get("name") or product_id, 80)
    cond = field.get("condicoes") or {}
    roles = _authorized_roles_text(field, getattr(inter, "guild", None))
    quantity_min = cond.get("quantidadeMin")
    quantity_min_text = f"{quantity_min} unidade" if quantity_min not in (None, "") else "1 unidade"
    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {emoji.zenyx2}\n-# Painel > Loja > Produtos > {name} > Configurações Extra"),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay("Gerencie as condições extras deste produto."),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay(
            "**Condições Atuais**\n"
            f"-# Valor mínimo: `{_value_or_dash(cond.get('valorMin'))}`\n"
            f"-# Valor máximo: `{_value_or_dash(cond.get('valorMax'))}`\n"
            f"-# Quantidade mínima: `{quantity_min_text}`\n"
            f"-# Quantidade máxima: `{_value_or_dash(cond.get('quantidadeMax'))}`\n"
            f"-# Cargos autorizados: `{roles}`"
        ),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Editar Valores", emoji=emoji.edit, custom_id=f"Promisse_EditarValores:{product_id}:{field_id}"),
            disnake.ui.Button(label="Resetar Cargos", emoji=emoji.reload, style=disnake.ButtonStyle.danger, custom_id=f"Promisse_ResetarCargos:{product_id}:{field_id}"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.RoleSelect(
                placeholder="Selecione os cargos autorizados a comprar",
                custom_id=f"Promisse_CargosAutorizados:{product_id}:{field_id}",
                min_values=0,
                max_values=25,
            )
        ),
        **_colour_kwargs(product),
    )
    return {
        "components": [
            container,
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id=f"Promisse_VoltarProduto:{product_id}:{field_id}")
            ),
        ]
    }


def build_advanced_panel(inter, product_id: str, field_id: str) -> dict:
    product, field = _product_and_field(product_id, field_id)
    info = product.get("info") or {}
    name = safe_textdisplay(field.get("name") or product.get("name") or product_id, 80)
    category = info.get("category_name") or "Não definido"
    banner = "Definido" if info.get("banner") else "Não definido"
    thumbnail = "Definido" if info.get("thumbnail") else "Não definido"
    role_id = info.get("required_role_id")
    role_text = "Não definido"
    if role_id and getattr(inter, "guild", None):
        role = inter.guild.get_role(int(role_id)) if str(role_id).isdigit() else None
        role_text = role.name if role else str(role_id)
    color = str(info.get("hex_color") or "#ADD8E6").upper()
    coupons_enabled = info.get("coupons_enabled", True)
    coupon_text = "Pode utilizar cupom nesse produto!" if coupons_enabled else "Cupons desativados neste produto."
    coupon_label = "Desativar Cupons" if coupons_enabled else "Ativar Cupons"

    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {emoji.zenyx2}\n-# Painel > Loja > Produtos > {name} > Configurações"),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay("Gerencie as configurações avançadas deste produto."),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay(
            "**Configurações Avançadas**\n"
            f"-# Categoria: `{category}`\n"
            f"-# Banner: `{banner}`\n"
            f"-# Miniatura: `{thumbnail}`\n"
            f"-# Cargo: `{role_text}`\n"
            f"-# Cor Embed: `{color}`\n"
            f"-# Cupom: `{coupon_text}`"
        ),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Banner", emoji=emoji.image, custom_id=f"Promisse_Banner:{product_id}:{field_id}"),
            disnake.ui.Button(label="Miniatura", emoji=emoji.image, custom_id=f"Promisse_Miniatura:{product_id}:{field_id}"),
            disnake.ui.Button(label="Cargo", emoji=emoji.role, custom_id=f"Promisse_CargoObrigatorio:{product_id}:{field_id}"),
            disnake.ui.Button(label="Cor Embed", emoji=emoji.colors, custom_id=f"Promisse_CorEmbed:{product_id}:{field_id}"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Categoria", emoji=emoji.flag, style=disnake.ButtonStyle.primary, custom_id=f"Promisse_Categoria:{product_id}:{field_id}"),
            disnake.ui.Button(label=coupon_label, emoji=emoji.on if coupons_enabled else emoji.off, style=disnake.ButtonStyle.danger if coupons_enabled else disnake.ButtonStyle.green, custom_id=f"Promisse_ToggleCupons:{product_id}:{field_id}"),
        ),
        **_colour_kwargs(product),
    )
    return {
        "components": [
            container,
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id=f"Promisse_VoltarProduto:{product_id}:{field_id}")
            ),
        ]
    }


class ConfigurarCampo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def panel(inter, product_id: str, field_id: str):
        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        if mode == "embed":
            return ConfigurarCampo._panel_embed(inter, product_id, field_id)
        return ConfigurarCampo._panel_components(inter, product_id, field_id)

    @staticmethod
    def _panel_components(inter, product_id: str, field_id: str) -> dict:
        product, field = _product_and_field(product_id, field_id)
        if not product or not field:
            from ..cog import GerenciarCamposCategorias
            return GerenciarCamposCategorias(inter.bot).panel(inter, product_id)

        header, body, conditions = _main_text(product_id, field_id, getattr(inter, "guild", None))
        return {
            "components": [
                disnake.ui.Container(
                    disnake.ui.TextDisplay(header),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(body),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(conditions),
                    disnake.ui.Separator(),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(label="Editar", emoji=emoji.edit, custom_id=f"Promisse_EditarProduto:{product_id}:{field_id}"),
                        disnake.ui.Button(label="Estoque", emoji=emoji.cardbox, custom_id=f"Loja_EstoqueCampo:{product_id}:{field_id}"),
                        disnake.ui.Button(label="Estilo de Entrega", emoji=emoji.information, custom_id=f"Promisse_ToggleEntrega:{product_id}:{field_id}"),
                        disnake.ui.Button(label="Config.Extra", emoji=emoji.settings2, custom_id=f"Promisse_ConfigExtra:{product_id}:{field_id}"),
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(label="Configurações", emoji=emoji.settings2, custom_id=f"Promisse_Configuracoes:{product_id}:{field_id}"),
                        disnake.ui.Button(label="Sincronizar", emoji=emoji.reload, custom_id=f"Promisse_Sincronizar:{product_id}:{field_id}"),
                        disnake.ui.Button(label="Deletar", emoji=emoji.delete, custom_id=f"Promisse_Deletar:{product_id}:{field_id}"),
                    ),
                    **_colour_kwargs(product),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Loja_Produtos")
                ),
            ]
        }

    @staticmethod
    def _panel_embed(inter, product_id: str, field_id: str) -> dict:
        product, field = _product_and_field(product_id, field_id)
        if not product or not field:
            from ..cog import GerenciarCamposCategorias
            return GerenciarCamposCategorias(inter.bot)._panel_embed(inter, product_id)
        header, body, conditions = _main_text(product_id, field_id, getattr(inter, "guild", None))
        embed = disnake.Embed(description=f"{header}\n\n{body}\n\n{conditions}", **_colour_kwargs(product, embed=True))
        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Editar", emoji=emoji.edit, custom_id=f"Promisse_EditarProduto:{product_id}:{field_id}"),
                disnake.ui.Button(label="Estoque", emoji=emoji.cardbox, custom_id=f"Loja_EstoqueCampo:{product_id}:{field_id}"),
                disnake.ui.Button(label="Estilo de Entrega", emoji=emoji.information, custom_id=f"Promisse_ToggleEntrega:{product_id}:{field_id}"),
                disnake.ui.Button(label="Config.Extra", emoji=emoji.settings2, custom_id=f"Promisse_ConfigExtra:{product_id}:{field_id}"),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Configurações", emoji=emoji.settings2, custom_id=f"Promisse_Configuracoes:{product_id}:{field_id}"),
                disnake.ui.Button(label="Sincronizar", emoji=emoji.reload, custom_id=f"Promisse_Sincronizar:{product_id}:{field_id}"),
                disnake.ui.Button(label="Deletar", emoji=emoji.delete, custom_id=f"Promisse_Deletar:{product_id}:{field_id}"),
            ),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id="Loja_Produtos")),
        ]
        return {"embed": embed, "components": components}


def setup(bot: commands.Bot):
    bot.add_cog(ConfigurarCampo(bot))
