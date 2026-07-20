import disnake
import requests
import io
import os
import re
from urllib.parse import urlparse, unquote
from typing import Any, Dict, List, Optional, Tuple

from functions.database import database
from functions.emoji import emoji
from ..anunciar import Anunciar
from .components.buttons import Buttons

# Precompiled token regex for container parsing
TOKEN_RE = re.compile(r"\{\{(.*?)\}\}")


class Builder:
    @staticmethod
    def _download_external_image(url: str) -> Optional[disnake.File]:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()

            parsed = urlparse(url)
            name = unquote(os.path.basename(parsed.path)) or "image"

            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            default_ext = None
            if content_type in ("image/jpeg", "image/jpg"):
                default_ext = ".jpg"
            elif content_type == "image/png":
                default_ext = ".png"
            elif content_type == "image/gif":
                default_ext = ".gif"
            elif content_type == "image/webp":
                default_ext = ".webp"

            if "." not in name and default_ext:
                name = f"{name}{default_ext}"
            elif "." not in name:
                name = f"{name}.png"
            return disnake.File(fp=io.BytesIO(resp.content), filename=name)
        except Exception:
            return None
    
    @staticmethod
    def _parse_color_to_int(color_text: str) -> Optional[int]:
        try:
            color_text = color_text.strip()
            if color_text.startswith("#"):
                return int(color_text[1:], 16)
            if color_text.lower().startswith("0x"):
                return int(color_text, 16)
            return int(color_text, 16)
        except Exception:
            return None

    @staticmethod
    def _parse_image_token(params: str) -> Optional[disnake.ui.MediaGallery]:
        url = None
        desc = None
        spoiler = False
        url_m = re.search(r"url='([^']+)'", params)
        if url_m:
            url = url_m.group(1)
        desc_m = re.search(r"desc='([^']*)'", params)
        if desc_m:
            desc = desc_m.group(1)
        if re.search(r"\bspoiler\b", params):
            spoiler = True
        if not url:
            return None
        return disnake.ui.MediaGallery(
            disnake.MediaGalleryItem(media=url, description=desc or None, spoiler=spoiler)
        )
        
    @staticmethod
    def _load_cfg() -> Dict[str, Any]:
        return database.get_document("messages_anunciar") or {}

    @staticmethod
    def _build_embed(msg_cfg: Dict[str, Any]) -> Optional[disnake.Embed]:
        embed_cfg: Dict[str, Any] = msg_cfg.get("embed") or {}
        has_any = any([
            embed_cfg.get("title"),
            embed_cfg.get("description"),
            embed_cfg.get("color"),
            embed_cfg.get("footer"),
        ])
        if not has_any:
            return None

        e = disnake.Embed()
        if embed_cfg.get("title"):
            e.title = embed_cfg.get("title")
        if embed_cfg.get("description"):
            e.description = embed_cfg.get("description")
        if embed_cfg.get("color"):
            try:
                color_str = embed_cfg.get("color").lstrip("#")
                e.color = int(color_str, 16)
            except Exception:
                pass
        if embed_cfg.get("footer"):
            e.set_footer(text=embed_cfg.get("footer"))

        images_cfg = {
            "banner": Anunciar._safe_get(msg_cfg, "embed.banner"),
            "thumbnail": Anunciar._safe_get(msg_cfg, "embed.thumbnail"),
        }
        if images_cfg.get("banner"):
            e.set_image(url=images_cfg["banner"])
        if images_cfg.get("thumbnail"):
            e.set_thumbnail(url=images_cfg["thumbnail"])
        return e

    @staticmethod
    def _build_buttons(msg_cfg: Dict[str, Any]) -> List[disnake.ui.ActionRow]:
        rows: List[disnake.ui.ActionRow] = []
        btns: List[Dict[str, Any]] = msg_cfg.get("buttons") or []
        current_row: List[disnake.ui.Button] = []

        for b in btns:
            label = b.get("label") or None
            data = b.get("button", {})
            btn_type = data.get("type", "disabled")
            style = Buttons._style_from_str(data.get("style"))
            emoji_raw = data.get("emoji")
            parsed_emoji = Buttons.processar_emoji(emoji_raw) if emoji_raw else None

            if btn_type == "url":
                button = disnake.ui.Button(label=label, style=disnake.ButtonStyle.url, url=data.get("url"), emoji=parsed_emoji)
            else:
                button = disnake.ui.Button(
                    label=label,
                    style=style,
                    emoji=parsed_emoji,
                    custom_id=f"Anunciar_RuntimeAction_Botao_{b.get('id')}",
                    disabled=(btn_type == "disabled" or data.get("disabled", False)),
                )

            current_row.append(button)
            if len(current_row) == 5:
                rows.append(disnake.ui.ActionRow(*current_row))
                current_row = []

        if current_row:
            rows.append(disnake.ui.ActionRow(*current_row))

        return rows

    @staticmethod
    def _parse_container(text: str) -> Tuple[List[Any], Optional[int]]:
        if not text:
            return [], None

        components: List[Any] = []
        accent_color_value: Optional[int] = None
        pos = 0
        for m in TOKEN_RE.finditer(text):
            if m.start() > pos:
                chunk = text[pos:m.start()].strip()
                if chunk:
                    components.append(disnake.ui.TextDisplay(chunk))

            inner = m.group(1).strip()
            if inner.lower() == "separator":
                components.append(disnake.ui.Separator())
            elif inner.lower().startswith("color:"):
                color_text = inner[6:].strip()
                accent_color_value = Builder._parse_color_to_int(color_text)
            elif inner.lower().startswith("image"):
                params = inner[5:].strip()
                gallery = Builder._parse_image_token(params)
                if gallery is not None:
                    components.append(gallery)
            pos = m.end()

        if pos < len(text):
            tail = text[pos:].strip()
            if tail:
                components.append(disnake.ui.TextDisplay(tail))

        return components, accent_color_value

    @staticmethod
    def build_from_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
        msg_cfg: Dict[str, Any] = cfg.get("message", {}) or {}

        is_v2 = bool(cfg.get("is_v2_component"))
        has_container = Anunciar._safe_get(msg_cfg, "container") is not None
        embed_obj = Builder._build_embed(msg_cfg)
        has_embed = embed_obj is not None
        content_text: Optional[str] = msg_cfg.get("content") or None
        button_rows = Builder._build_buttons(msg_cfg)
        external_url: Optional[str] = msg_cfg.get("externalImage") or None
        has_external_image = bool(external_url)
        has_buttons = bool(button_rows)
        
        # Se há apenas imagem externa (com ou sem botões) sem content, embed ou container,
        # força modo v2 para enviar corretamente
        if not is_v2 and not has_container and not content_text and not has_embed and has_external_image:
            is_v2 = True

        if is_v2 or has_container:
            components: List[Any] = []
            if external_url:
                components.append(
                    disnake.ui.MediaGallery(
                        disnake.MediaGalleryItem(media=external_url)
                    )
                )
            if content_text:
                components.append(disnake.ui.TextDisplay(content_text))

            if has_container:
                parsed_components, accent_color_value = Builder._parse_container(msg_cfg.get("container"))
                inner = parsed_components or [disnake.ui.TextDisplay(msg_cfg.get("container"))]
                container_kwargs: Dict[str, Any] = {}
                if accent_color_value is not None:
                    container_kwargs["accent_colour"] = disnake.Colour(accent_color_value)
                components.append(disnake.ui.Container(*inner, **container_kwargs))

            components.extend(button_rows)
            return {
                "mode": "v2",
                "components": components,
                "flags": disnake.MessageFlags(is_components_v2=True),
            }

        # embed/default mode
        result: Dict[str, Any] = {
            "mode": "embed",
            "content": content_text,
            "embed": embed_obj,
            "components": button_rows if button_rows else None,
        }

        if external_url:
            file = Builder._download_external_image(external_url)
            if file is not None:
                result["files"] = [file]

        return result

    @staticmethod
    def build() -> Dict[str, Any]:
        cfg = Builder._load_cfg()
        return Builder.build_from_cfg(cfg)