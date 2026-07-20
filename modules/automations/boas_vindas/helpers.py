import io
import json
from typing import Optional

import aiohttp
import disnake

from functions.database import database as db

def carregar_config() -> dict:
    """Carrega a configuração do banco de dados."""
    dados = db.get_document("automations_boas_vindas") or {}
    
    if not isinstance(dados, dict):
        dados = {}
    # Valores padrão
    if "mensagem" not in dados:
        dados["mensagem"] = "Bem-vindo {user} ao {nameserver}! Agora somos {servercount}."
    if "tempo_segundos" not in dados:
        dados["tempo_segundos"] = 0
    if "usar_componentes_v2" not in dados:
        dados["usar_componentes_v2"] = False
    if "ativado" not in dados:
        dados["ativado"] = True
    if "modo_envio" not in dados:
        dados["modo_envio"] = "v2" if bool(dados.get("usar_componentes_v2", False)) else "v1"
    if "rota_envio" not in dados:
        dados["rota_envio"] = "canal"
    return dados

def salvar_config(data: dict) -> None:
    """Salva a configuração no banco de dados."""
    atual = carregar_config()
    atual.update(data or {})
    db.save_document("automations_boas_vindas", {}, atual)

def obter_canal_boas_vindas(guild: disnake.Guild) -> Optional[disnake.TextChannel]:
    """Obtém o canal de boas-vindas configurado para o servidor."""
    definicoes = db.get_document("canais") or {}
        
    canal_id = definicoes.get("canal_de_boas_vindas")
    try:
        canal_id_int = int(canal_id) if canal_id else None
    except Exception:
        canal_id_int = None
    if not canal_id_int:
        return None
    canal = guild.get_channel(canal_id_int)
    if isinstance(canal, disnake.TextChannel):
        return canal
    return None

def formatar_mensagem(template: str, member: disnake.Member) -> str:
    """Formata a mensagem de boas-vindas com as variáveis."""
    guild = member.guild
    substituicoes = {
        "{user}": member.mention,
        "{nameserver}": guild.name if guild else "servidor",
        "{nameuser}": getattr(member, "name", str(member.id)),
        "{servercount}": str(getattr(guild, "member_count", "")),
    }
    conteudo = template or ""
    for chave, valor in substituicoes.items():
        conteudo = conteudo.replace(chave, valor)
    return conteudo

def parse_hex_to_colour(value: Optional[str]) -> Optional[disnake.Colour]:
    """Converte uma cor hexadecimal em um objeto disnake.Colour."""
    if not value:
        return None
    try:
        s = str(value).strip().lower()
        if s.startswith("0x"):
            s = s[2:]
        if s.startswith("#"):
            s = s[1:]
        if len(s) != 6:
            return None
        int_val = int(s, 16)
        return disnake.Colour(int_val)
    except Exception:
        return None

def system_badge_row() -> disnake.ui.ActionRow:
    """Cria uma ActionRow com um badge de 'Mensagem do Sistema'."""
    return disnake.ui.ActionRow(
        disnake.ui.Button(label="Mensagem do Sistema", style=disnake.ButtonStyle.grey, custom_id="BV_SystemBadge", disabled=True)
    )

def montar_embed_preview(conteudo: str, cfg: dict) -> disnake.Embed:
    """Monta um embed de prévia com base na configuração."""
    embed = disnake.Embed(description=conteudo)
    titulo = (cfg.get("embed_titulo") or "").strip()
    if titulo:
        embed.title = titulo
    banner = (cfg.get("embed_banner_url") or "").strip()
    if banner.startswith("http://") or banner.startswith("https://"):
        try:
            embed.set_image(banner)
        except Exception:
            pass
    thumb = (cfg.get("embed_thumb_url") or "").strip()
    if thumb.startswith("http://") or thumb.startswith("https://"):
        try:
            embed.set_thumbnail(thumb)
        except Exception:
            pass
    cor_hex = (cfg.get("embed_cor") or "").strip().lstrip('#')
    if cor_hex:
        try:
            embed.colour = int(cor_hex, 16)
        except Exception:
            pass
    else:
        try:
            colors = db.get_document("custom_colors") or {}
            primary_hex = (colors.get("primary") or "").strip().lstrip('#')
            if primary_hex:
                embed.colour = int(primary_hex, 16)
        except Exception:
            pass
    return embed

def montar_container_preview(conteudo: str, cfg: dict) -> disnake.ui.Container:
    """Monta um container V2 de prévia com base na configuração."""
    children = [disnake.ui.TextDisplay(conteudo)]
    url = (cfg.get("v2_imagem_url") or "").strip()
    if url.startswith("http://") or url.startswith("https://"):
        try:
            children.append(disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small))
            children.append(disnake.ui.MediaGallery(disnake.MediaGalleryItem({"media": {"url": url}, "description": "", "spoiler": False})))
        except Exception:
            pass
    cor_container = parse_hex_to_colour(cfg.get("v2_cor_container"))
    if not cor_container:
        try:
            colors = db.get_document("custom_colors") or {}
            primary_hex = colors.get("primary")
        except Exception:
            primary_hex = None
        cor_container = parse_hex_to_colour(primary_hex)
    return disnake.ui.Container(*children, accent_colour=cor_container) if cor_container else disnake.ui.Container(*children)

async def baixar_imagem(url: Optional[str]) -> Optional[disnake.File]:
    """Baixa uma imagem de uma URL e a retorna como disnake.File."""
    url = (url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    bytes_data = await resp.read()
                    return disnake.File(io.BytesIO(bytes_data), filename="boas_vindas.png")
    except Exception:
        return None
    return None
