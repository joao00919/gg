from __future__ import annotations

import re
import time
from typing import Any

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.interaction_runtime import respond_panel
from functions.permission_matrix import has_capability
from functions.utils import utils
from .configurar import ConfigurarProduto


def _interaction_values(inter: disnake.ModalInteraction) -> dict[str, Any]:
    values: dict[str, Any] = {}
    values.update(getattr(inter, "text_values", {}) or {})
    values.update(getattr(inter, "resolved_values", {}) or {})
    return values


def _first(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _e(name: str, fallback: str = "config"):
    return getattr(emoji, name, getattr(emoji, fallback, None))


def _parse_price(value: Any) -> float:
    raw = str(value or "").strip().replace("R$", "").replace(" ", "")
    if not raw:
        return 0.0
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    raw = re.sub(r"[^0-9.-]", "", raw)
    try:
        return max(0.0, round(float(raw), 2))
    except (TypeError, ValueError):
        raise ValueError("Informe um valor válido. Exemplo: 19,90")


def _default_field(*, field_id: str, product_name: str, price: float) -> dict:
    now = int(time.time())
    return {
        "id": field_id,
        "name": product_name,
        "price": float(price),
        "emoji": None,
        "pre_description": None,
        "description": None,
        "instructions": None,
        "category_id": None,
        "created_at": now,
        "updated_at": now,
        "advanced": {},
        "stock": [],
        "estoque": [],
        "stock_style": "traditional",
        "cargos": {"adicionar": [], "remover": [], "authorized": []},
        "condicoes": {
            "valorMin": None,
            "valorMax": None,
            "quantidadeMin": None,
            "quantidadeMax": None,
        },
    }


def build_product_payload(
    *,
    product_id: str,
    name: str,
    description: str | None,
    banner: str | None,
    hex_color: str | None,
    delivery_type: str | None,
    price: float | None = None,
) -> dict:
    """Gera o documento completo usado pelo painel, checkout e automações."""
    now = int(time.time())
    normalized_delivery = str(delivery_type or "automatic").strip().lower()
    if normalized_delivery not in {"automatic", "manual"}:
        normalized_delivery = "automatic"

    product = {
        "id": product_id,
        "name": name.strip(),
        "active": True,
        "promisse_style": True,
        "info": {
            "description": (description or "").strip() or None,
            "banner": banner,
            "thumbnail": None,
            "hex_color": hex_color,
            "delivery_type": normalized_delivery,
            "created_at": now,
            "updated_at": now,
            "purchasesIds": [],
            "total_paid": 0,
            "low_stock": False,
            "required_role_id": None,
            "coupons_enabled": True,
            "category_name": None,
            "display_preferences": {
                "show_sales": True,
                "show_options": True,
                "show_stock": True,
                "cart_duration_minutes": 30,
                "store_hours": "",
                "transcript_enabled": False,
            },
            "buy_button": {"label": "Comprar", "emoji": _e("cart")},
        },
        "campos": {},
        "categorias": {},
        "messages": [],
        "cupons": {},
        "related_products": [],
        "promotion": {"enabled": False, "disabled_by_low_stock": False},
        "automation": {"low_stock_threshold": 5},
    }
    if price is not None:
        field_id = utils.gerar_id()
        field = _default_field(
            field_id=field_id,
            product_name=name.strip(),
            price=float(price),
        )
        normalized_description = (description or "").strip() or f"{name.strip()} disponível para compra."
        field["pre_description"] = normalized_description
        field["description"] = normalized_description
        product["campos"][field_id] = field
    return product


def create_method_panel(inter: disnake.Interaction) -> dict:
    colors = db.get_document("custom_colors") or {}
    kwargs: dict[str, Any] = {}
    primary = colors.get("primary")
    if primary:
        try:
            kwargs["accent_colour"] = disnake.Colour(int(str(primary).replace("#", ""), 16))
        except Exception:
            pass
    return {
        "components": [
            disnake.ui.Container(
                disnake.ui.TextDisplay(
                    f"# {_e('zenyx2')}\n-# Painel > Loja > Produtos > **Criar Produto**"
                ),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "## Como você quer criar o produto?\n"
                    "• **Manual** — preencha nome, descrição, valor e banner em um único formulário.\n\n"
                    "• **Criar com IA** — receba uma sugestão de nome, descrição e valor para revisar."
                ),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Criar Manualmente",
                        style=disnake.ButtonStyle.secondary,
                        emoji=_e("edit"),
                        custom_id="Loja_CriarProduto_Manual",
                    ),
                    disnake.ui.Button(
                        label="Criar com IA",
                        style=disnake.ButtonStyle.primary,
                        emoji=_e("cloud", "sparkles"),
                        custom_id="Loja_CriarProduto_IA",
                    ),
                ),
                **kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.secondary,
                    emoji=_e("back"),
                    custom_id="Loja_Produtos",
                )
            ),
        ]
    }


async def _save_and_show(
    inter: disnake.ModalInteraction,
    *,
    name: str,
    price: float,
    description: str | None = None,
    banner: str | None = None,
) -> None:
    product_id = utils.gerar_id()
    product = build_product_payload(
        product_id=product_id,
        name=name,
        description=description,
        banner=banner,
        hex_color="#ADD8E6",
        delivery_type="automatic",
        price=price,
    )
    products = db.get_document("loja_products") or {}
    products[product_id] = product
    db.save_document("loja_products", products)
    saved = (db.get_document("loja_products") or {}).get(product_id)
    if not saved:
        return await inter.response.send_message(
            f"{_e('wrong')} Não foi possível salvar o produto.", ephemeral=True
        )

    await inter.response.defer(with_message=True, ephemeral=True)
    panel = ConfigurarProduto.panel(inter, product_id)
    panel = dict(panel)
    panel.pop("flags", None)
    await inter.edit_original_message(content=None, embed=None, **panel)


class CreateProductModal(disnake.ui.Modal):
    """Modal manual igual ao fluxo mostrado no vídeo."""

    def __init__(self):
        super().__init__(
            title="Criar Novo Produto",
            custom_id="create_product_modal",
            components=[
                disnake.ui.TextInput(
                    label="Nome do Produto",
                    placeholder="Ex.: Netflix 1 Mês",
                    custom_id="product_name",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100,
                ),
                disnake.ui.TextInput(
                    label="Descrição do Produto",
                    placeholder="Descreva o produto, validade, benefícios e observações.",
                    custom_id="product_description",
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    min_length=3,
                    max_length=1800,
                ),
                disnake.ui.TextInput(
                    label="Valor do Produto (R$)",
                    placeholder="Ex.: 20,00",
                    custom_id="product_price",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=20,
                ),
                disnake.ui.TextInput(
                    label="Banner do Produto (opcional)",
                    placeholder="https://exemplo.com/banner.png",
                    custom_id="product_banner",
                    style=disnake.TextInputStyle.short,
                    required=False,
                    max_length=500,
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        if getattr(inter, "user", None) is not None and not has_capability(inter, "products"):
            return await inter.response.send_message(
                f"{_e('wrong')} Você não tem permissão para criar produtos.", ephemeral=True
            )
        values = _interaction_values(inter)
        name = str(_first(values.get("product_name")) or "").strip()
        if not name:
            return await inter.response.send_message(
                f"{_e('wrong')} Informe o nome do produto.", ephemeral=True
            )
        description = str(_first(values.get("product_description")) or "").strip()
        if len(description) < 3:
            return await inter.response.send_message(
                f"{_e('wrong')} Informe uma descrição válida para o produto.", ephemeral=True
            )
        banner = str(_first(values.get("product_banner")) or "").strip() or None
        if banner and not banner.lower().startswith(("http://", "https://")):
            return await inter.response.send_message(
                f"{_e('wrong')} O banner precisa ser uma URL iniciada por http:// ou https://.",
                ephemeral=True,
            )
        try:
            price = _parse_price(_first(values.get("product_price")))
        except ValueError as exc:
            return await inter.response.send_message(f"{_e('wrong')} {exc}", ephemeral=True)
        await _save_and_show(inter, name=name, price=price, description=description, banner=banner)


class CreateProductAIModal(disnake.ui.Modal):
    """Assistente local: cria uma sugestão revisável sem depender de API externa."""

    def __init__(self):
        super().__init__(
            title="Criar Produto com IA",
            custom_id="Loja_CriarProduto_IA_Modal",
            components=[
                disnake.ui.TextInput(
                    label="O que você quer vender?",
                    placeholder="Ex.: Assinatura Netflix por 30 dias",
                    custom_id="idea",
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=700,
                ),
                disnake.ui.TextInput(
                    label="Valor desejado (opcional)",
                    placeholder="Ex.: 25,90",
                    custom_id="price",
                    style=disnake.TextInputStyle.short,
                    required=False,
                    max_length=20,
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        if getattr(inter, "user", None) is not None and not has_capability(inter, "products"):
            return await inter.response.send_message(
                f"{_e('wrong')} Você não tem permissão para criar produtos.", ephemeral=True
            )
        values = _interaction_values(inter)
        idea = " ".join(str(_first(values.get("idea")) or "").strip().split())
        if not idea:
            return await inter.response.send_message(
                f"{_e('wrong')} Descreva o produto.", ephemeral=True
            )
        raw_price = _first(values.get("price"))
        try:
            price = _parse_price(raw_price) if str(raw_price or "").strip() else 0.0
        except ValueError as exc:
            return await inter.response.send_message(f"{_e('wrong')} {exc}", ephemeral=True)
        name = idea[:100]
        description = (
            f"{idea}. Produto criado pelo assistente de configuração. "
            "Revise a descrição, o estoque e o estilo de entrega antes de publicar."
        )[:2000]
        await _save_and_show(inter, name=name, price=price, description=description)


class CreateProduct(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid == "Loja_CriarProduto":
            if getattr(inter, "user", None) is not None and not has_capability(inter, "products"):
                return await inter.response.send_message(
                    f"{_e('wrong')} Você não tem permissão para criar produtos.", ephemeral=True
                )
            return await respond_panel(inter, create_method_panel(inter), prefer_edit=True)
        if cid == "Loja_CriarProduto_Manual":
            return await inter.response.send_modal(CreateProductModal())
        if cid == "Loja_CriarProduto_IA":
            return await inter.response.send_modal(CreateProductAIModal())


def setup(bot: commands.Bot):
    bot.add_cog(CreateProduct(bot))
