from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.permission_matrix import has_capability
from functions.utils import utils
from functions.loja_products import get_product_description
from modules.loja.products.product.configurar import ConfigurarProduto

DOC_NAME = "loja_product_panels"
MAX_PRODUCTS_PER_PANEL = 25


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _e(name: str, fallback: str = "config"):
    return getattr(emoji, name, getattr(emoji, fallback, None))


def get_panels() -> dict[str, dict[str, Any]]:
    data = db.get_document(DOC_NAME) or {}
    return data if isinstance(data, dict) else {}


def save_panels(panels: dict[str, dict[str, Any]]) -> None:
    db.save_document(DOC_NAME, panels)


def create_panel(name: str, created_by: int) -> tuple[str, dict[str, Any]]:
    panels = get_panels()
    panel_id = utils.gerar_id()
    panel = {
        "id": panel_id,
        "name": (name or "Painel de Produtos").strip()[:100] or "Painel de Produtos",
        "description": "Selecione um produto abaixo para ver as opções disponíveis.",
        "product_ids": [],
        "product_emojis": {},
        "active": True,
        "messages": [],
        "created_by": str(created_by),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    panels[panel_id] = panel
    save_panels(panels)
    return panel_id, panel


def resolve_panel(value: Optional[str]) -> str:
    return str(value or "").rsplit(" — ", 1)[-1].strip()


def panel_autocomplete_values(text: str) -> list[str]:
    query = (text or "").lower()
    values: list[str] = []
    for panel_id, panel in get_panels().items():
        label = f"{panel.get('name') or 'Painel'} — {panel_id}"
        if not query or query in label.lower():
            values.append(label[:100])
    return values[:25]


def _safe_emoji(value: Any, fallback: Any = None):
    if not value:
        return fallback
    try:
        return disnake.PartialEmoji.from_str(str(value))
    except Exception:
        return fallback


def _active_products() -> dict[str, dict[str, Any]]:
    products = db.get_document("loja_products") or {}
    return {
        str(product_id): product
        for product_id, product in products.items()
        if isinstance(product, dict) and product.get("active", True)
    }


def _product_name(product: dict, product_id: str = "") -> str:
    return str(product.get("name") or product_id or "Produto")[:100]


def _panel_product_emoji(panel: dict, product_id: str, product: dict):
    configured = (panel.get("product_emojis") or {}).get(product_id)
    product_emoji = configured or (product.get("info") or {}).get("emoji")
    return _safe_emoji(product_emoji, _safe_emoji(_e("cart")))


def _product_option(product_id: str, product: dict, panel: Optional[dict] = None) -> disnake.SelectOption:
    info = product.get("info") or {}
    fields = product.get("campos") or {}
    description = get_product_description(product, fallback=False)
    if not description:
        description = f"{len(fields)} opção(ões) disponível(is)"
    description = " ".join(description.split())[:100]
    return disnake.SelectOption(
        label=_product_name(product, product_id),
        description=description,
        value=product_id,
        emoji=_panel_product_emoji(panel or {}, product_id, product),
    )


def _accent_kwargs() -> dict:
    colors = db.get_document("custom_colors") or {}
    primary = colors.get("primary")
    if primary:
        try:
            return {"accent_colour": disnake.Colour(int(str(primary).replace("#", ""), 16))}
        except Exception:
            pass
    return {}


def _panel_description(panel: dict) -> str:
    text = str((panel or {}).get("description") or "").strip()
    return text or "Selecione um produto abaixo para continuar."


def _panel_color(panel: dict):
    raw = str((panel or {}).get("hex_color") or "").strip()
    if not raw:
        raw = str((db.get_document("custom_colors") or {}).get("primary") or "").strip()
    if raw:
        try:
            return int(raw.replace("#", ""), 16)
        except (TypeError, ValueError):
            return None
    return None


def _panel_banner(panel: dict) -> str | None:
    value = str((panel or {}).get("banner") or "").strip()
    return value if value.startswith(("http://", "https://")) else None


def _components_payload(*children) -> dict:
    return {
        "components": [disnake.ui.Container(*children, **_accent_kwargs())],
        "flags": disnake.MessageFlags(is_components_v2=True),
    }


def _editable_payload(payload: dict) -> dict:
    """Remove flags imutáveis ao editar uma mensagem já criada."""
    clean = dict(payload)
    clean.pop("flags", None)
    return clean


def _panel_select(panel_id: str, panel: dict, products: dict, selected: list[str]) -> disnake.ui.StringSelect:
    options = [_product_option(pid, products[pid], panel) for pid in selected]
    return disnake.ui.StringSelect(
        custom_id=f"ZynexProductPanel_Buy:{panel_id}",
        placeholder="Selecione um Produto",
        min_values=1,
        max_values=1,
        options=options,
    )


def _public_panel_data(panel_id: str):
    panel = get_panels().get(panel_id)
    if not panel:
        raise ValueError("Painel não encontrado.")
    if not panel.get("active", True):
        raise ValueError("Este painel está desativado.")
    products = _active_products()
    selected = [str(pid) for pid in panel.get("product_ids", []) if str(pid) in products][:MAX_PRODUCTS_PER_PANEL]
    if not selected:
        raise ValueError("Adicione pelo menos um produto antes de publicar o painel.")
    return panel, products, selected


def build_public_components(panel_id: str, *, image_inside: bool = False) -> list:
    panel, products, selected = _public_panel_data(panel_id)
    select = _panel_select(panel_id, panel, products, selected)
    title = str(panel.get("name") or "Produtos").strip() or "Produtos"
    description = _panel_description(panel)
    banner = _panel_banner(panel)
    inner = [
        disnake.ui.TextDisplay(f"# {_e('zenyx2')} {title}\n{description}"),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(select),
    ]
    if image_inside and banner:
        inner.insert(0, disnake.ui.MediaGallery(disnake.MediaGalleryItem(media=banner)))
    kwargs = _accent_kwargs()
    color = _panel_color(panel)
    if color is not None:
        kwargs["accent_colour"] = disnake.Colour(color)
    components = []
    if banner and not image_inside:
        components.append(disnake.ui.MediaGallery(disnake.MediaGalleryItem(media=banner)))
    components.append(disnake.ui.Container(*inner, **kwargs))
    return components


def build_public_embed(panel_id: str, *, personalized: bool = True) -> tuple[disnake.Embed, list]:
    panel, products, selected = _public_panel_data(panel_id)
    select = _panel_select(panel_id, panel, products, selected)
    kwargs = {}
    if personalized:
        color = _panel_color(panel)
        if color is not None:
            kwargs["color"] = color
    else:
        kwargs["color"] = disnake.Color.blurple()
    embed = disnake.Embed(
        title=str(panel.get("name") or "Produtos"),
        description=_panel_description(panel),
        **kwargs,
    )
    if personalized and _panel_banner(panel):
        embed.set_image(url=_panel_banner(panel))
    return embed, [disnake.ui.ActionRow(select)]


def build_public_text(panel_id: str) -> tuple[str, list]:
    panel, products, selected = _public_panel_data(panel_id)
    select = _panel_select(panel_id, panel, products, selected)
    content = f"**{str(panel.get('name') or 'Produtos')}**\n{_panel_description(panel)}"[:1900]
    return content, [disnake.ui.ActionRow(select)]


def build_publish_style_payload(panel_id: str, channel_id: int) -> dict:
    panel = get_panels().get(panel_id)
    if not panel:
        raise ValueError("Painel não encontrado.")
    text = (
        f"# {_e('zenyx2')}\n-# Publicar Painel > **Escolher Modo**\n\n"
        "**Modo Texto**\n-# Mensagem simples em texto sem embed\n"
        "**Modo Legacy**\n-# Embed tradicional\n"
        "**Modo Legacy (Personalizado)**\n-# Usa descrição, banner e cor configurados\n"
        "**Modo Container V2**\n-# Imagem fora ou dentro do container"
    )
    return _components_payload(
        disnake.ui.TextDisplay(text),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Modo Texto Simples", emoji=_e("textc"), custom_id=f"ZynexProductPanel_PublishStyle:text:{panel_id}:{channel_id}"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Modo Legacy", emoji=_e("textc"), custom_id=f"ZynexProductPanel_PublishStyle:legacy:{panel_id}:{channel_id}"),
            disnake.ui.Button(label="Modo Legacy (Personalizado)", emoji=_e("wand"), custom_id=f"ZynexProductPanel_PublishStyle:legacy_custom:{panel_id}:{channel_id}"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Container (Imagem Fora)", emoji=_e("image", "pic"), custom_id=f"ZynexProductPanel_PublishStyle:container_outside:{panel_id}:{channel_id}"),
            disnake.ui.Button(label="Container (Imagem Dentro)", emoji=_e("image", "pic"), custom_id=f"ZynexProductPanel_PublishStyle:container_inside:{panel_id}:{channel_id}"),
        ),
    )


def build_admin_payload(panel_id: str) -> dict:
    panel = get_panels().get(panel_id)
    if not panel:
        raise ValueError("Painel não encontrado.")
    title = str(panel.get("name") or "Painel de Produtos")
    description = _panel_description(panel)
    text = (
        f"# {_e('zenyx2')}\n"
        f"-# Painel > Loja > Produtos > {title}\n\n"
        "**Informações do Painel**\n"
        f"-# ID do Painel: `{panel_id}`\n"
        f"-# Título: `{title}`\n"
        "-# Descrição:\n"
        f"```\n{description[:1600]}\n```"
    )
    return _components_payload(
        disnake.ui.TextDisplay(text),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Configurar Embed",
                emoji=_e("wand"),
                custom_id=f"ZynexProductPanel_Edit:{panel_id}",
            ),
            disnake.ui.Button(
                label="Configurar Produtos",
                emoji=_e("cart"),
                custom_id=f"ZynexProductPanel_Products:{panel_id}",
            ),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Atualizar Painel",
                emoji=_e("reload"),
                style=disnake.ButtonStyle.primary,
                custom_id=f"ZynexProductPanel_Sync:{panel_id}",
            ),
            disnake.ui.Button(
                label="Deletar",
                emoji=_e("delete"),
                style=disnake.ButtonStyle.danger,
                custom_id=f"ZynexProductPanel_Delete:{panel_id}",
            ),
        ),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Voltar",
                emoji=_e("back"),
                custom_id=f"ZynexProductPanel_BackList:{panel_id}",
            )
        ),
    )


def build_products_payload(panel_id: str) -> dict:
    panel = get_panels().get(panel_id)
    if not panel:
        raise ValueError("Painel não encontrado.")
    products = _active_products()
    selected = [str(pid) for pid in panel.get("product_ids", []) if str(pid) in products]
    lines: list[str] = []
    for index, product_id in enumerate(selected, start=1):
        icon = (panel.get("product_emojis") or {}).get(product_id) or _e("cart")
        lines.append(f"{icon} `{index:02d}` • **{_product_name(products[product_id], product_id)}** • `{product_id}`")
    products_text = "\n".join(lines) if lines else "-# Nenhum produto cadastrado neste painel."

    if selected:
        emoji_options = [_product_option(pid, products[pid], panel) for pid in selected[:25]]
        emoji_select = disnake.ui.StringSelect(
            custom_id=f"ZynexProductPanel_EmojiSelect:{panel_id}",
            placeholder="Alterar Emoji do Produto",
            min_values=1,
            max_values=1,
            options=emoji_options,
        )
    else:
        emoji_select = disnake.ui.StringSelect(
            custom_id=f"ZynexProductPanel_EmojiSelect:{panel_id}",
            placeholder="Alterar Emoji do Produto",
            disabled=True,
            options=[disnake.SelectOption(label="Nenhum produto cadastrado", value="none")],
        )

    text = (
        f"# {_e('zenyx2')}\n"
        f"-# Painel > Loja > Produtos > {panel.get('name') or 'Painel'} > Gerenciar Produtos\n\n"
        "**Produtos cadastrados no Painel**\n"
        f"{products_text}\n\n"
        "-# Para trocar o emoji de algum produto, selecione ele no menu abaixo"
    )
    return _components_payload(
        disnake.ui.TextDisplay(text),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Adicionar Produto",
                emoji=_e("plus"),
                style=disnake.ButtonStyle.green,
                custom_id=f"ZynexProductPanel_AddOpen:{panel_id}",
            ),
            disnake.ui.Button(
                label="Remover Produto",
                emoji=_e("delete"),
                custom_id=f"ZynexProductPanel_RemoveOpen:{panel_id}",
                disabled=not bool(selected),
            ),
        ),
        disnake.ui.ActionRow(emoji_select),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Sequência",
                emoji=_e("route"),
                custom_id=f"ZynexProductPanel_Sequence:{panel_id}",
                disabled=len(selected) < 2,
            ),
            disnake.ui.Button(
                label="Sincronizar",
                emoji=_e("reload"),
                style=disnake.ButtonStyle.primary,
                custom_id=f"ZynexProductPanel_Sync:{panel_id}",
            ),
        ),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Voltar",
                emoji=_e("back"),
                custom_id=f"ZynexProductPanel_Back:{panel_id}",
            )
        ),
    )


def build_delete_payload(panel_id: str) -> dict:
    panel = get_panels().get(panel_id) or {}
    return _components_payload(
        disnake.ui.TextDisplay(
            f"# {_e('warn')} Deletar Painel\n"
            f"Tem certeza que deseja deletar **{panel.get('name') or 'este painel'}**?\n"
            "-# As mensagens já publicadas também serão removidas quando forem encontradas."
        ),
        disnake.ui.Separator(),
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Deletar",
                emoji=_e("delete"),
                style=disnake.ButtonStyle.danger,
                custom_id=f"ZynexProductPanel_ConfirmDelete:{panel_id}",
            ),
            disnake.ui.Button(
                label="Cancelar",
                emoji=_e("back"),
                custom_id=f"ZynexProductPanel_Back:{panel_id}",
            ),
        ),
    )


async def publish_panel(
    *,
    panel_id: str,
    channel: disnake.abc.Messageable,
    guild_id: int,
    author_id: int,
    style: str | None = None,
) -> disnake.Message:
    style = str(style or "container_outside")
    if style == "text":
        content, components = build_public_text(panel_id)
        msg = await channel.send(content=content, components=components)
    elif style == "legacy":
        embed, components = build_public_embed(panel_id, personalized=False)
        msg = await channel.send(embed=embed, components=components)
    elif style == "legacy_custom":
        embed, components = build_public_embed(panel_id, personalized=True)
        msg = await channel.send(embed=embed, components=components)
    elif style == "container_inside":
        msg = await channel.send(
            components=build_public_components(panel_id, image_inside=True),
            flags=disnake.MessageFlags(is_components_v2=True),
        )
    else:
        style = "container_outside"
        msg = await channel.send(
            components=build_public_components(panel_id, image_inside=False),
            flags=disnake.MessageFlags(is_components_v2=True),
        )
    panels = get_panels()
    panel = panels.get(panel_id)
    if panel is not None:
        records = panel.setdefault("messages", [])
        record = {
            "message_id": int(msg.id),
            "channel_id": int(getattr(channel, "id", 0)),
            "guild_id": int(guild_id),
            "published_by": str(author_id),
            "mode": style,
            "created_at": _now_iso(),
        }
        if not any(int(item.get("message_id", 0) or 0) == int(msg.id) for item in records):
            records.append(record)
        panel["updated_at"] = _now_iso()
        panels[panel_id] = panel
        save_panels(panels)
    return msg


async def sync_published_messages(bot: commands.Bot, panel_id: str) -> tuple[int, int]:
    panels = get_panels()
    panel = panels.get(panel_id)
    if not panel:
        return 0, 0
    success = 0
    failed = 0
    valid_records: list[dict] = []
    current_mode = (db.get_document("custom_mode") or {}).get("mode", "components")
    for record in list(panel.get("messages") or []):
        try:
            channel_id = int(record.get("channel_id", 0) or 0)
            message_id = int(record.get("message_id", 0) or 0)
            channel = bot.get_channel(channel_id)
            if channel is None:
                channel = await bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
            mode = str(record.get("mode") or current_mode)
            if mode == "text":
                content, components = build_public_text(panel_id)
                await message.edit(content=content, embed=None, components=components)
            elif mode == "legacy":
                embed, components = build_public_embed(panel_id, personalized=False)
                await message.edit(content=None, embed=embed, components=components)
            elif mode in {"legacy_custom", "embed"}:
                embed, components = build_public_embed(panel_id, personalized=True)
                await message.edit(content=None, embed=embed, components=components)
                mode = "legacy_custom"
            elif mode == "container_inside":
                await message.edit(content=None, embed=None, components=build_public_components(panel_id, image_inside=True))
            else:
                mode = "container_outside"
                await message.edit(content=None, embed=None, components=build_public_components(panel_id, image_inside=False))
            record["mode"] = mode
            record["synced_at"] = _now_iso()
            valid_records.append(record)
            success += 1
        except Exception:
            failed += 1
    panel["messages"] = valid_records
    panel["updated_at"] = _now_iso()
    panels[panel_id] = panel
    save_panels(panels)
    return success, failed


class EditProductPanelModal(disnake.ui.Modal):
    def __init__(self, panel_id: str, panel: dict):
        self.panel_id = panel_id
        super().__init__(
            title="Configurar Painel",
            custom_id=f"ZynexProductPanel_EditModal:{panel_id}",
            components=[
                disnake.ui.TextInput(
                    label="Título do Painel",
                    custom_id="panel_name",
                    value=str(panel.get("name") or "Painel de Produtos")[:100],
                    max_length=100,
                ),
                disnake.ui.TextInput(
                    label="Descrição do Painel",
                    custom_id="panel_description",
                    value=str(panel.get("description") or "")[:2000],
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    min_length=3,
                    max_length=2000,
                ),
                disnake.ui.TextInput(
                    label="Banner do Painel (opcional)",
                    custom_id="panel_banner",
                    value=str(panel.get("banner") or "")[:500],
                    required=False,
                    max_length=500,
                ),
                disnake.ui.TextInput(
                    label="Cor HEX (opcional)",
                    custom_id="panel_color",
                    placeholder="#5865F2",
                    value=str(panel.get("hex_color") or "")[:7],
                    required=False,
                    max_length=7,
                ),
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        if not has_capability(inter, "products"):
            return await inter.response.send_message(
                f"{_e('wrong')} Você não possui permissão para gerenciar painéis.", ephemeral=True
            )
        panels = get_panels()
        panel = panels.get(self.panel_id)
        if not panel:
            return await inter.response.send_message(f"{_e('wrong')} Painel não encontrado.", ephemeral=True)
        values = dict(getattr(inter, "text_values", {}) or {})
        panel["name"] = str(values.get("panel_name") or "Painel de Produtos").strip()[:100]
        panel["description"] = str(values.get("panel_description") or "").strip()[:2000] or "Selecione um produto abaixo para continuar."
        banner = str(values.get("panel_banner") or "").strip()
        panel["banner"] = banner if banner.startswith(("http://", "https://")) else None
        color = str(values.get("panel_color") or "").strip()
        panel["hex_color"] = color if color.startswith("#") and len(color) == 7 else None
        panel["updated_at"] = _now_iso()
        panels[self.panel_id] = panel
        save_panels(panels)
        await inter.response.defer()
        await inter.edit_original_message(content=None, embed=None, **_editable_payload(build_admin_payload(self.panel_id)))


class ProductEmojiModal(disnake.ui.Modal):
    def __init__(self, panel_id: str, product_id: str, panel: dict):
        self.panel_id = panel_id
        self.product_id = product_id
        current = str((panel.get("product_emojis") or {}).get(product_id) or "")
        super().__init__(
            title="Alterar Emoji do Produto",
            custom_id=f"ZynexProductPanel_EmojiModal:{panel_id}:{product_id}",
            components=[
                disnake.ui.TextInput(
                    label="Emoji personalizado",
                    custom_id="product_emoji",
                    placeholder="Ex.: <:cart:1525692023540154520>",
                    value=current[:100],
                    required=False,
                    max_length=100,
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        panels = get_panels()
        panel = panels.get(self.panel_id)
        if not panel:
            return await inter.response.send_message(f"{_e('wrong')} Painel não encontrado.", ephemeral=True)
        value = str((getattr(inter, "text_values", {}) or {}).get("product_emoji") or "").strip()
        mapping = panel.setdefault("product_emojis", {})
        if value:
            if _safe_emoji(value) is None:
                return await inter.response.send_message(
                    f"{_e('wrong')} Informe um emoji válido no formato `<:nome:id>`.", ephemeral=True
                )
            mapping[self.product_id] = value
        else:
            mapping.pop(self.product_id, None)
        panel["updated_at"] = _now_iso()
        panels[self.panel_id] = panel
        save_panels(panels)
        await inter.response.defer()
        await inter.edit_original_message(content=None, embed=None, **_editable_payload(build_products_payload(self.panel_id)))


class ProductSequenceModal(disnake.ui.Modal):
    def __init__(self, panel_id: str, panel: dict, products: dict):
        self.panel_id = panel_id
        current = [str(pid) for pid in panel.get("product_ids", []) if str(pid) in products]
        readable = "\n".join(f"{index}. {pid}" for index, pid in enumerate(current, start=1))
        super().__init__(
            title="Alterar Sequência dos Produtos",
            custom_id=f"ZynexProductPanel_SequenceModal:{panel_id}",
            components=[
                disnake.ui.TextInput(
                    label="IDs na ordem desejada",
                    custom_id="product_sequence",
                    value=readable[:2000],
                    style=disnake.TextInputStyle.paragraph,
                    max_length=2000,
                    placeholder="1. ID_DO_PRODUTO\n2. OUTRO_ID",
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        panels = get_panels()
        panel = panels.get(self.panel_id)
        if not panel:
            return await inter.response.send_message(f"{_e('wrong')} Painel não encontrado.", ephemeral=True)
        current = [str(pid) for pid in panel.get("product_ids", [])]
        raw = str((getattr(inter, "text_values", {}) or {}).get("product_sequence") or "")
        requested: list[str] = []
        for line in raw.replace(",", "\n").splitlines():
            clean = line.strip()
            if "." in clean and clean.split(".", 1)[0].strip().isdigit():
                clean = clean.split(".", 1)[1].strip()
            if clean and clean in current and clean not in requested:
                requested.append(clean)
        requested.extend(pid for pid in current if pid not in requested)
        panel["product_ids"] = requested[:MAX_PRODUCTS_PER_PANEL]
        panel["updated_at"] = _now_iso()
        panels[self.panel_id] = panel
        save_panels(panels)
        await inter.response.defer()
        await inter.edit_original_message(content=None, embed=None, **_editable_payload(build_products_payload(self.panel_id)))


class ProductPanelsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _edit(self, inter: disnake.MessageInteraction, payload: dict) -> None:
        await inter.edit_original_message(content=None, embed=None, **_editable_payload(payload))

    async def _product_select_screen(self, inter: disnake.MessageInteraction, panel_id: str, *, removing: bool) -> None:
        panel = get_panels().get(panel_id) or {}
        products = _active_products()
        selected = [str(pid) for pid in panel.get("product_ids", []) if str(pid) in products]
        if removing:
            ids = selected
            title = "Remover Produto"
            description = "Selecione um ou mais produtos para remover deste painel."
            placeholder = "Selecione os produtos para remover"
            custom_id = f"ZynexProductPanel_RemoveSelect:{panel_id}"
        else:
            ids = [pid for pid in products if pid not in selected][:MAX_PRODUCTS_PER_PANEL - len(selected)]
            title = "Adicionar Produto"
            description = "Selecione um ou mais produtos para adicionar neste painel."
            placeholder = "Selecione os produtos para adicionar"
            custom_id = f"ZynexProductPanel_AddSelect:{panel_id}"
        if not ids:
            return await inter.response.send_message(
                f"{_e('information')} Nenhum produto disponível para esta ação.", ephemeral=True
            )
        options = [_product_option(pid, products[pid], panel) for pid in ids[:25]]
        select = disnake.ui.StringSelect(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=1,
            max_values=len(options),
            options=options,
        )
        payload = _components_payload(
            disnake.ui.TextDisplay(
                f"# {_e('zenyx2')} {title}\n"
                f"-# Painel > Loja > Produtos > {panel.get('name') or 'Painel'} > {title}\n\n"
                f"{description}"
            ),
            disnake.ui.Separator(),
            disnake.ui.ActionRow(select),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    emoji=_e("back"),
                    custom_id=f"ZynexProductPanel_Products:{panel_id}",
                )
            ),
        )
        await inter.response.defer()
        await self._edit(inter, payload)

    @commands.Cog.listener("on_dropdown")
    async def dropdowns(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid.startswith("ZynexProductPanel_Buy:"):
            panel_id = cid.split(":", 1)[1]
            panel = get_panels().get(panel_id)
            product_id = str(inter.values[0]) if inter.values else ""
            products = _active_products()
            product = products.get(product_id)
            if not panel or not panel.get("active", True):
                return await inter.response.send_message(f"{_e('wrong')} Este painel está desativado.", ephemeral=True)
            if product_id not in [str(v) for v in panel.get("product_ids", [])] or not product:
                return await inter.response.send_message(f"{_e('wrong')} Produto indisponível.", ephemeral=True)
            mode = (db.get_document("custom_mode") or {}).get("mode", "components")
            if mode == "embed":
                embed = ConfigurarProduto._build_legacy_embed(product, inter.guild)
                button = disnake.ui.Button(
                    label=(product.get("info") or {}).get("buy_button", {}).get("label", "Comprar"),
                    style=disnake.ButtonStyle.grey,
                    emoji=_e("cart"),
                    custom_id=f"buy_product:{product_id}",
                )
                return await inter.response.send_message(embed=embed, components=[disnake.ui.ActionRow(button)], ephemeral=True)
            components = ConfigurarProduto._build_container_components(product, image_inside=False, product_id=product_id)
            return await inter.response.send_message(
                components=components,
                flags=disnake.MessageFlags(is_components_v2=True),
                ephemeral=True,
            )

        if not cid.startswith("ZynexProductPanel_"):
            return
        if not has_capability(inter, "products"):
            return await inter.response.send_message(
                f"{_e('wrong')} Você não possui permissão para gerenciar painéis.", ephemeral=True
            )
        action, panel_id = cid.split(":", 1)
        panels = get_panels()
        panel = panels.get(panel_id)
        if not panel:
            return await inter.response.send_message(f"{_e('wrong')} Painel não encontrado.", ephemeral=True)
        products = _active_products()

        if action.endswith("_AddSelect"):
            current = [str(pid) for pid in panel.get("product_ids", [])]
            for product_id in [str(v) for v in inter.values]:
                if product_id in products and product_id not in current and len(current) < MAX_PRODUCTS_PER_PANEL:
                    current.append(product_id)
            panel["product_ids"] = current
            message = f"{_e('correct')} Produto(s) adicionado(s) ao painel."
        elif action.endswith("_RemoveSelect"):
            removing = {str(v) for v in inter.values}
            panel["product_ids"] = [str(pid) for pid in panel.get("product_ids", []) if str(pid) not in removing]
            for product_id in removing:
                panel.setdefault("product_emojis", {}).pop(product_id, None)
            message = f"{_e('correct')} Produto(s) removido(s) do painel."
        elif action.endswith("_EmojiSelect"):
            product_id = str(inter.values[0]) if inter.values else ""
            if product_id not in [str(pid) for pid in panel.get("product_ids", [])]:
                return await inter.response.send_message(f"{_e('wrong')} Produto inválido.", ephemeral=True)
            return await inter.response.send_modal(ProductEmojiModal(panel_id, product_id, panel))
        else:
            return

        panel["updated_at"] = _now_iso()
        panels[panel_id] = panel
        save_panels(panels)
        await inter.response.defer()
        await self._edit(inter, build_products_payload(panel_id))
        await inter.followup.send(message, ephemeral=True)

    @commands.Cog.listener("on_button_click")
    async def buttons(self, inter: disnake.MessageInteraction):
        cid = str(inter.component.custom_id or "")
        if cid.startswith("ZynexProductPanel_PublishStyle:"):
            if not has_capability(inter, "products"):
                return await inter.response.send_message(f"{_e('wrong')} Você não possui permissão para publicar painéis.", ephemeral=True)
            try:
                _, style, panel_id, channel_id = cid.split(":", 3)
                panel = get_panels().get(panel_id)
                if not panel:
                    return await inter.response.send_message(f"{_e('wrong')} Painel não encontrado.", ephemeral=True)
                channel = inter.guild.get_channel(int(channel_id))
                if channel is None:
                    return await inter.response.send_message(f"{_e('wrong')} Canal não encontrado.", ephemeral=True)
                await inter.response.defer(ephemeral=True)
                msg = await publish_panel(
                    panel_id=panel_id, channel=channel, guild_id=inter.guild.id,
                    author_id=inter.author.id, style=style,
                )
                return await inter.followup.send(
                    f"{_e('correct')} Painel publicado em {channel.mention}. [Ir para o painel]({msg.jump_url})",
                    ephemeral=True,
                )
            except Exception as exc:
                return await inter.followup.send(f"{_e('wrong')} Não foi possível publicar o painel: {str(exc)[:200]}", ephemeral=True)
        if not cid.startswith("ZynexProductPanel_"):
            return
        if not has_capability(inter, "products"):
            return await inter.response.send_message(
                f"{_e('wrong')} Você não possui permissão para gerenciar painéis.", ephemeral=True
            )
        action, panel_id = cid.split(":", 1)
        panels = get_panels()
        panel = panels.get(panel_id)
        if not panel:
            return await inter.response.send_message(f"{_e('wrong')} Painel não encontrado.", ephemeral=True)

        if action.endswith("_Edit"):
            return await inter.response.send_modal(EditProductPanelModal(panel_id, panel))
        if action.endswith("_Products"):
            await inter.response.defer()
            return await self._edit(inter, build_products_payload(panel_id))
        if action.endswith("_Back"):
            await inter.response.defer()
            return await self._edit(inter, build_admin_payload(panel_id))
        if action.endswith("_BackList"):
            from modules.loja.products.cog import GerenciarProdutos
            payload = GerenciarProdutos(self.bot).panel(inter)
            payload = _editable_payload(payload)
            await inter.response.defer()
            return await self._edit(inter, payload)
        if action.endswith("_AddOpen"):
            return await self._product_select_screen(inter, panel_id, removing=False)
        if action.endswith("_RemoveOpen"):
            return await self._product_select_screen(inter, panel_id, removing=True)
        if action.endswith("_Sequence"):
            return await inter.response.send_modal(ProductSequenceModal(panel_id, panel, _active_products()))
        if action.endswith("_Sync"):
            await inter.response.defer(ephemeral=True)
            success, failed = await sync_published_messages(self.bot, panel_id)
            await inter.followup.send(
                f"{_e('correct')} Painel sincronizado. Atualizados: **{success}**"
                + (f" • Falhas removidas: **{failed}**" if failed else ""),
                ephemeral=True,
            )
            return
        if action.endswith("_Delete"):
            await inter.response.defer()
            return await self._edit(inter, build_delete_payload(panel_id))
        if action.endswith("_ConfirmDelete"):
            # Tenta apagar as publicações conhecidas antes de remover o registro.
            for record in list(panel.get("messages") or []):
                try:
                    channel_id = int(record.get("channel_id", 0) or 0)
                    message_id = int(record.get("message_id", 0) or 0)
                    channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                except Exception:
                    pass
            panels.pop(panel_id, None)
            save_panels(panels)
            return await inter.response.edit_message(
                content=f"{_e('correct')} Painel deletado com sucesso!",
                embed=None,
                components=[],
            )


def setup(bot: commands.Bot):
    bot.add_cog(ProductPanelsCog(bot))
