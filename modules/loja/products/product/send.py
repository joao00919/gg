import disnake
from disnake.ext import commands
from functions.database import database as db
from functions.emoji import emoji
from functions.text_utils import wrap_text
from functions.utils import utils
from functions.promotions import get_effective_price
from functions.loja_products import get_product_description, ensure_product_description
from PIL import Image
from io import BytesIO
import requests
import requests.exceptions
import re


class SendProduct(commands.Cog):
    """Sistema simplificado de envio de produtos - Legacy e Container"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Valida se a URL é uma URL de imagem válida e acessível"""
        if not url or not isinstance(url, str):
            return False
        
        # Verificar se é uma URL válida
        url_pattern = re.compile(
            r'^https?://'  # http:// ou https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domínio
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # porta opcional
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            return False
        
        # Verificar extensões de imagem comuns
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        url_lower = url.lower()
        if not any(url_lower.endswith(ext) or ext in url_lower.split('?')[0] for ext in image_extensions):
            # Pode ser uma URL sem extensão explícita, tentar validar via HEAD request
            try:
                resp = requests.head(url, timeout=5, allow_redirects=True)
                content_type = resp.headers.get('content-type', '').lower()
                if 'image' not in content_type:
                    return False
            except Exception:
                return False
        
        return True
    
    def _format_price(self, price: float) -> str:
        """Formata preço para padrão brasileiro"""
        return f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _price_text(self, product: dict) -> str:
        campos = product.get("campos") or {}
        prices = []
        for field in campos.values():
            try:
                prices.append(float((field or {}).get("price", 0) or 0))
            except (TypeError, ValueError):
                continue
        if not prices:
            return self._format_price(0)
        low, high = min(prices), max(prices)
        if low == high:
            return self._format_price(low)
        return f"{self._format_price(low)} - {self._format_price(high)}"

    def _build_text_content(self, product: dict) -> str:
        name = str(product.get("name") or "Produto").strip() or "Produto"
        description = get_product_description(product)
        option_count = len(product.get("campos") or {})
        return (
            f"**{name}**\n"
            f"{description}\n\n"
            f"**{self._price_text(product)}**\n"
            f"{option_count} {'opção disponível' if option_count == 1 else 'opções disponíveis'}"
        )[:1900]

    def _build_basic_legacy_embed(self, product: dict) -> disnake.Embed:
        name = str(product.get("name") or "Produto").strip() or "Produto"
        description = get_product_description(product)
        option_count = len(product.get("campos") or {})
        embed = disnake.Embed(
            title=name,
            description=description,
            color=disnake.Color.blurple(),
        )
        embed.add_field(name="Preço", value=f"`{self._price_text(product)}`", inline=True)
        embed.add_field(
            name="Opções",
            value=f"`{option_count} {'disponível' if option_count == 1 else 'disponíveis'}`",
            inline=True,
        )
        return embed
    
    @staticmethod
    def _resolve_target_channel(guild: disnake.Guild, channel_id: int | None):
        if guild is None or not channel_id:
            return None
        resolver = getattr(guild, "get_channel_or_thread", None)
        if callable(resolver):
            channel = resolver(int(channel_id))
            if channel is not None:
                return channel
        return guild.get_channel(int(channel_id))

    def _safe_get_emoji(self, emoji_str, fallback=emoji.cart):
        """Valida e retorna emoji seguro, usando fallback se inválido"""
        if not emoji_str:
            return fallback
        
        if isinstance(emoji_str, str):
            # Se for emoji unicode simples, retornar direto
            if len(emoji_str) <= 2 and not emoji_str.startswith("<"):
                return emoji_str
            # Se for formato de emoji customizado (<:name:id> ou <a:name:id>)
            if emoji_str.startswith("<"):
                try:
                    partial_emoji = disnake.PartialEmoji.from_str(emoji_str)
                    # Validar se tem ID válido
                    if partial_emoji.id:
                        return partial_emoji
                    else:
                        return fallback
                except:
                    return fallback
            # Se for string simples, retornar como está
            return emoji_str
        
        # Se já for um objeto PartialEmoji, validar
        if isinstance(emoji_str, disnake.PartialEmoji):
            # Se não tem ID, pode ser inválido
            if not emoji_str.id:
                return fallback
            return emoji_str
        
        return fallback
    
    def _create_buy_button(self, product_id: str) -> list:
        """Cria botões de compra e dúvida (se configurado)"""
        # Obter produto para pegar configuração do botão customizado
        products = db.get_document("loja_products")
        product = products.get(product_id) if product_id else {}
        
        info = product.get("info", {}) if product else {}
        button_config = info.get("buy_button", {})
        active = product.get("active", True) if product else False
        button_label = button_config.get("label", "Comprar") if active else "Produto indisponível"
        button_emoji_str = button_config.get("emoji", emoji.cart)
        
        # Preparar emoji do botão usando função segura
        btn_emoji = self._safe_get_emoji(button_emoji_str)
        
        # Verificar se o botão de dúvidas está habilitado
        doubt_config = db.get_document("loja_doubt_button")
        
        buttons = [
            disnake.ui.Button(
                label=button_label,
                emoji=btn_emoji,
                style=disnake.ButtonStyle.grey,
                custom_id=f"buy_product:{product_id}",
                disabled=not active,
            )
        ]
        
        # Adicionar botão de dúvidas se estiver habilitado
        if doubt_config.get("enabled") and doubt_config.get("channel_id"):
            doubt_emoji = doubt_config.get("button_emoji")
            if doubt_emoji and isinstance(doubt_emoji, str) and doubt_emoji.startswith("<"):
                try:
                    doubt_emoji = disnake.PartialEmoji.from_str(doubt_emoji)
                except:
                    doubt_emoji = "❓"
            elif not doubt_emoji:
                doubt_emoji = "❓"
            
            buttons.append(
                disnake.ui.Button(
                    label=doubt_config.get("button_label", "Dúvidas"),
                    emoji=doubt_emoji,
                    style=disnake.ButtonStyle.secondary,
                    custom_id="product_doubt_button"
                )
            )
        
        return [disnake.ui.ActionRow(*buttons)]
    
    def _build_legacy_embed(self, product: dict, guild: disnake.Guild, formatted_desc: bool = True) -> disnake.Embed:
        """Constrói embed no modo Legacy com footer do servidor
        formatted_desc=True -> descrição completa com quebras de linha
        formatted_desc=False -> descrição padrão Discord (sem formatação especial)
        """
        product_name = product.get("name", "Produto")
        description = get_product_description(product)
        hex_color = product.get("info", {}).get("hex_color")
        banner = product.get("info", {}).get("banner")
        campos = product.get("campos", {})
        
        # Calcular preços
        prices = [get_effective_price(product, campo) for campo in campos.values()]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        if min_price == max_price:
            price_text = self._format_price(min_price)
        else:
            price_text = f"{self._format_price(min_price)} - {self._format_price(max_price)}"
        
        # Criar embed
        embed_kwargs = {}
        if hex_color:
            try:
                embed_kwargs["color"] = disnake.Color(int(hex_color.replace("#", ""), 16))
            except:
                pass
        
        # Aplicar quebra de linha se formatada
        if formatted_desc and description:
            description = wrap_text(description, max_line_length=50)
        
        embed = disnake.Embed(
            title=product_name,
            description=description if description else "Produto disponível para compra",
            **embed_kwargs
        )
        
        # Adicionar informações
        embed.add_field(
            name=f"{emoji.dollar} Preço",
            value=f"`{price_text}`",
            inline=True
        )
        
        # Obter preferências de exibição
        info = product.get("info", {})
        display_prefs = info.get("display_preferences", {})
        show_options = display_prefs.get("show_options", True)
        show_sales = display_prefs.get("show_sales", True)
        
        # Adicionar opções primeiro (se habilitado)
        if show_options:
            embed.add_field(
                name=f"{emoji.embed} Opções",
                value=f"`{len(campos)} disponível`" if len(campos) == 1 else f"`{len(campos)} disponíveis`",
                inline=True
            )
        
        # Adicionar vendas depois (se habilitado)
        if show_sales:
            purchases_count = len(info.get("purchasesIds", []))
            if purchases_count > 0:
                embed.add_field(
                    name=f"{emoji.dollar} Vendas",
                    value=f"`{purchases_count} {'venda realizada' if purchases_count == 1 else 'vendas realizadas'}`",
                    inline=True
                )
        
        # Banner - validar URL antes de usar
        if banner and self._is_valid_image_url(banner):
            embed.set_image(url=banner)
        
        # Footer com informações do servidor
        icon_url = guild.icon.url if guild.icon else None
        embed.set_footer(text=guild.name, icon_url=icon_url)
        embed.timestamp = disnake.utils.utcnow()
        
        return embed
    
    def _build_container(self, product: dict, image_inside: bool = False, product_id: str = "", formatted_desc: bool = True, banner_gallery: disnake.ui.MediaGallery | None = None, wrap_len: int | None = None, force_emoji_cart: bool = False) -> list:
        """Constrói container moderno com MediaGallery
        image_inside=True -> imagem dentro do container
        image_inside=False -> imagem fora (acima) do container
        formatted_desc=True -> descrição completa com quebras de linha
        formatted_desc=False -> descrição padrão Discord (sem formatação especial)
        """
        product_name = product.get("name", "Produto")
        description = get_product_description(product)
        hex_color = product.get("info", {}).get("hex_color")
        banner = product.get("info", {}).get("banner")
        campos = product.get("campos", {})
        
        # Calcular preços
        prices = [get_effective_price(product, campo) for campo in campos.values()]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        if min_price == max_price:
            price_text = self._format_price(min_price)
        else:
            price_text = f"{self._format_price(min_price)} - {self._format_price(max_price)}"
        
        # Componentes
        components = []
        # Container principal
        container_kwargs = {}
        if hex_color:
            try:
                container_kwargs["accent_colour"] = disnake.Colour(int(hex_color.replace("#", ""), 16))
            except:
                pass
        
        # Textos com formatação baseada em formatted_desc
        title_text = f"**{product_name}**"
        # Sempre adicionar descrição se existir
        if description:
            if formatted_desc:
                description = wrap_text(description, max_line_length=wrap_len or 50)
            title_text += f"\n{description}"
        
        # Obter preferências de exibição
        info = product.get("info", {})
        display_prefs = info.get("display_preferences", {})
        show_options = display_prefs.get("show_options", True)
        show_sales = display_prefs.get("show_sales", True)
        
        # Construir informações de preço
        price_info_parts = [f"**{price_text}**"]
        
        # Adicionar opções primeiro (se habilitado)
        if show_options:
            price_info_parts.append(f"-# {len(campos)} {'opção' if len(campos) == 1 else 'opções'} {'disponível' if len(campos) == 1 else 'disponíveis'}")
        
        # Adicionar vendas depois (se habilitado)
        if show_sales:
            purchases_count = len(info.get("purchasesIds", []))
            if purchases_count > 0:
                price_info_parts.append(f"-# {purchases_count} {'venda realizada' if purchases_count == 1 else 'vendas realizadas'}")

        price_info_text = "\n".join(price_info_parts)
        
        # Obter configuração do botão customizado
        button_config = info.get("buy_button", {})
        button_label = button_config.get("label", "Comprar")
        
        # Se force_emoji_cart for True, usar emoji.cart diretamente
        if force_emoji_cart:
            btn_emoji_preview = emoji.cart
        else:
            button_emoji_str = button_config.get("emoji", emoji.cart)
            # Preparar emoji do botão usando função segura
            btn_emoji_preview = self._safe_get_emoji(button_emoji_str)

        # Montar elementos internos do container
        inner_items = []
        if image_inside and banner:
            # Só adicionar se tiver banner_gallery processado ou URL válida
            if banner_gallery is not None:
                inner_items.append(banner_gallery)
            elif self._is_valid_image_url(banner):
                inner_items.append(
                    disnake.ui.MediaGallery(
                        disnake.MediaGalleryItem(media=banner)
                    )
                )
        inner_items.append(disnake.ui.TextDisplay(title_text))
        inner_items.append(disnake.ui.Separator())
        inner_items.append(
            disnake.ui.Section(
                disnake.ui.TextDisplay(price_info_text),
                accessory=disnake.ui.Button(
                    label=button_label,
                    emoji=btn_emoji_preview,
                    style=disnake.ButtonStyle.grey,
                    custom_id=f"buy_product:{product_id}"
                )
            )
        )

        container = disnake.ui.Container(
            *inner_items,
            **container_kwargs
        )

        # Se imagem for fora, adiciona acima do container
        if (not image_inside) and banner:
            # Só adicionar se tiver banner_gallery processado ou URL válida
            if banner_gallery is not None:
                components.append(banner_gallery)
            elif self._is_valid_image_url(banner):
                components.append(
                    disnake.ui.MediaGallery(
                        disnake.MediaGalleryItem(media=banner)
                    )
                )
        components.append(container)
        return components
    
    def _build_channel_selector(self, product_id: str, guild: disnake.Guild) -> disnake.ui.Container:
        """Constrói seletor de canal onde a mensagem será enviada"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
        container_kwargs = {}
        if primary_color_hex:
            container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
        
        return disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Publicar Produto > **Selecionar Canal**"),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay(
                "Escolha o canal onde deseja publicar a mensagem do produto:\n"
                "-# Selecione um canal de texto do servidor"
            ),
            disnake.ui.ActionRow(
                disnake.ui.ChannelSelect(
                    placeholder="Selecione o canal",
                    custom_id=f"select_channel:{product_id}",
                    channel_types=[disnake.ChannelType.text]
                )
            ),
            **container_kwargs
        )
    
    def _build_mode_selector(self, product_id: str, channel_id: str) -> disnake.ui.Container:
        """Exibe os cinco estilos de publicação usados pelo fluxo da loja."""
        colors = db.get_document("custom_colors") or {}
        container_kwargs = {}
        primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
        if primary_color_hex:
            try:
                container_kwargs["accent_colour"] = disnake.Colour(int(str(primary_color_hex).replace("#", ""), 16))
            except (TypeError, ValueError):
                pass

        return disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {getattr(emoji, 'zenyx2', emoji.z0)}\n-# Publicar Produto > **Escolher Modo**"),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay(
                "**Modo Texto**\n"
                "-# Mensagem simples em texto sem embed\n"
                "**Modo Legacy**\n"
                "-# Embed tradicional com informações do produto\n"
                "**Modo Legacy (Personalizado)**\n"
                "-# Usa descrição, banner, cor e botão configurados no produto\n"
                "**Modo Container V2**\n"
                "-# Escolha a imagem fora ou dentro do container"
            ),
            disnake.ui.Separator(),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Modo Texto Simples",
                    emoji=getattr(emoji, "textc", getattr(emoji, "speech", None)),
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"send_mode_text:formatted:normal:{product_id}:{channel_id}",
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Modo Legacy",
                    emoji=getattr(emoji, "embed", getattr(emoji, "textc", None)),
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"send_mode_legacy_basic:formatted:normal:{product_id}:{channel_id}",
                ),
                disnake.ui.Button(
                    label="Modo Legacy (Personalizado)",
                    emoji=getattr(emoji, "wand", getattr(emoji, "embed", None)),
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"send_select_desc_format:legacy:{product_id}:{channel_id}",
                ),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Container (Imagem Fora)",
                    emoji=getattr(emoji, "image", getattr(emoji, "pic", None)),
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"send_select_size:container_outside:{product_id}:{channel_id}",
                ),
                disnake.ui.Button(
                    label="Container (Imagem Dentro)",
                    emoji=getattr(emoji, "image", getattr(emoji, "pic", None)),
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"send_select_size:container_inside:{product_id}:{channel_id}",
                ),
            ),
            **container_kwargs,
        )

    def _build_size_selector(self, product_id: str, channel_id: str, mode: str) -> disnake.ui.Container:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
        container_kwargs = {}
        if primary_color_hex:
            container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

        return disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Publicar Produto > **Escolher Tamanho da Imagem**"),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay(
                "Selecione o tamanho do banner que será usado na mensagem:\n"
                "-# Small: menor largura (ideal para compactar)\n"
                "-# Medium: largura média (ex. 512px)\n"
                "-# Normal: tamanho original"
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Small",
                    emoji=emoji.image if hasattr(emoji, 'image') else None,
                    style=disnake.ButtonStyle.grey,
                    custom_id=f"send_select_desc_format:{mode}:small:{product_id}:{channel_id}"
                ),
                disnake.ui.Button(
                    label="Medium",
                    emoji=emoji.image if hasattr(emoji, 'image') else None,
                    style=disnake.ButtonStyle.blurple,
                    custom_id=f"send_select_desc_format:{mode}:medium:{product_id}:{channel_id}"
                ),
                disnake.ui.Button(
                    label="Normal",
                    emoji=emoji.image if hasattr(emoji, 'image') else None,
                    style=disnake.ButtonStyle.green,
                    custom_id=f"send_select_desc_format:{mode}:normal:{product_id}:{channel_id}"
                )
            ),
            **container_kwargs
        )

    def _build_banner_gallery(self, banner_url: str, size: str) -> tuple[disnake.ui.MediaGallery | None, list[disnake.File]]:
        """Constrói MediaGallery com banner processado. Retorna None se houver erro."""
        if not banner_url or not self._is_valid_image_url(banner_url):
            return None, []
        
        try:
            resp = requests.get(banner_url, timeout=10)
            resp.raise_for_status()
            
            # Verificar content-type
            content_type = resp.headers.get('content-type', '').lower()
            if 'image' not in content_type:
                return None, []
            
            buf_in = BytesIO(resp.content)
            im = Image.open(buf_in)
            
            # Validar que é uma imagem válida
            im.verify()
            im = Image.open(buf_in)  # Reabrir após verify
            
            w, h = im.size
            filename = "banner.png"
            target_w = None
            if size == "small":
                target_w = 320
                filename = "banner_small.png"
            elif size == "medium":
                filename = "banner_medium.png"
                if w > 512:
                    target_w = 512
                elif w > 320:
                    target_w = 400
                else:
                    target_w = None
            else:
                filename = "banner.png"

            if target_w is not None and w > target_w:
                new_h = int(h * (target_w / w))
                im = im.resize((target_w, new_h), Image.LANCZOS)

            out = BytesIO()
            im.save(out, format="PNG")
            out.seek(0)
            file = disnake.File(out, filename=filename)
            gallery = disnake.ui.MediaGallery(
                disnake.MediaGalleryItem(media=f"attachment://{filename}", description="Banner")
            )
            return gallery, [file]
        except requests.exceptions.HTTPError as e:
            # Se for 404 (imagem não encontrada), apenas retornar None silenciosamente
            if e.response and e.response.status_code == 404:
                return None, []
            # Para outros erros HTTP, logar mas não quebrar
            print(f"Erro HTTP ao processar banner {banner_url}: {e.response.status_code if e.response else 'Unknown'}")
            return None, []
        except Exception as e:
            # Outros erros (timeout, conexão, etc) - logar mas não quebrar
            # Não logar erros comuns como 404 para não poluir o console
            error_msg = str(e).lower()
            if "404" not in error_msg and "not found" not in error_msg:
                print(f"Erro ao processar banner {banner_url}: {e}")
            return None, []

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Handler para publicar produto (entrada principal)
        if custom_id.startswith("Loja_PublicarProduto:"):
            product_id = custom_id.split(":", 1)[1]
            
            # Mostrar seletor de canal primeiro
            await inter.response.defer(ephemeral=True)
            container = self._build_channel_selector(product_id, inter.guild)
            await inter.followup.send(
                components=[container],
                ephemeral=True,
                flags=disnake.MessageFlags(is_components_v2=True)
            )
            return
        
        # Handler para seleção de tamanho após modo
        if custom_id.startswith("send_select_size:"):
            parts = custom_id.split(":")
            mode = parts[1]
            product_id = parts[2]
            channel_id = parts[3]
            await inter.response.defer()
            # Se não for container, pular etapa de tamanho
            if mode == "legacy":
                colors = db.get_document("custom_colors")
                primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
                container_kwargs = {}
                if primary_color_hex:
                    container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
                container = disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Publicar Produto > **Formatação da Descrição**"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        "**Descrição Formatada**\n"
                        "-# Exibe a descrição completa com todas as quebras de linha\n"
                        "**Descrição Normal**\n"
                        "-# Segue o padrão do Discord (texto corrido)"
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Formatada",
                            emoji=emoji.correct,
                            style=disnake.ButtonStyle.green,
                            custom_id=f"send_mode_{mode}:formatted:normal:{product_id}:{channel_id}"
                        ),
                        disnake.ui.Button(
                            label="Normal",
                            emoji=emoji.information,
                            style=disnake.ButtonStyle.grey,
                            custom_id=f"send_mode_{mode}:normal:normal:{product_id}:{channel_id}"
                        )
                    ),
                    **container_kwargs
                )
                await inter.edit_original_message(
                    components=[container],
                    flags=disnake.MessageFlags(is_components_v2=True)
                )
                return

            # Para container: só mostrar etapa de tamanho se houver banner
            products = db.get_document("loja_products")
            product = products.get(product_id)
            banner_url = product.get("info", {}).get("banner") if product else None
            if not banner_url:
                # Ir direto para formatação com tamanho normal
                colors = db.get_document("custom_colors")
                primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
                container_kwargs = {}
                if primary_color_hex:
                    container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
                container = disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Publicar Produto > **Formatação da Descrição**"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        "**Descrição Formatada**\n"
                        "-# Exibe a descrição completa com todas as quebras de linha\n"
                        "**Descrição Normal**\n"
                        "-# Segue o padrão do Discord (texto corrido)"
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Formatada",
                            emoji=emoji.correct,
                            style=disnake.ButtonStyle.green,
                            custom_id=f"send_mode_{mode}:formatted:normal:{product_id}:{channel_id}"
                        ),
                        disnake.ui.Button(
                            label="Normal",
                            emoji=emoji.information,
                            style=disnake.ButtonStyle.grey,
                            custom_id=f"send_mode_{mode}:normal:normal:{product_id}:{channel_id}"
                        )
                    ),
                    **container_kwargs
                )
                await inter.edit_original_message(
                    components=[container],
                    flags=disnake.MessageFlags(is_components_v2=True)
                )
                return

            # Banner existe: mostrar seletor de tamanho
            container = self._build_size_selector(product_id, channel_id, mode)
            await inter.edit_original_message(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True)
            )
            return

        # Handler para seleção de formatação de descrição
        if custom_id.startswith("send_select_desc_format:"):
            parts = custom_id.split(":")
            mode = parts[1]  # legacy, container_outside, container_inside
            # Suporta chamadas com ou sem parâmetro de tamanho
            if len(parts) >= 5:
                size = parts[2]  # small, medium, normal
                product_id = parts[3]
                channel_id = int(parts[4]) if len(parts) > 4 else None
            else:
                size = "normal"
                product_id = parts[2]
                channel_id = int(parts[3]) if len(parts) > 3 else None
            
            # Mostrar seletor de formatação
            colors = db.get_document("custom_colors")
            primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
            container_kwargs = {}
            if primary_color_hex:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
            
            await inter.response.defer()
            container = disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Publicar Produto > **Formatação da Descrição**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "**Descrição Formatada**\n"
                    "-# Exibe a descrição completa com todas as quebras de linha\n"
                    "**Descrição Normal**\n"
                    "-# Segue o padrão do Discord (texto corrido)"
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Formatada",
                        emoji=emoji.correct,
                        style=disnake.ButtonStyle.green,
                        custom_id=f"send_mode_{mode}:formatted:{size}:{product_id}:{channel_id}"
                    ),
                    disnake.ui.Button(
                        label="Normal",
                        emoji=emoji.information,
                        style=disnake.ButtonStyle.grey,
                        custom_id=f"send_mode_{mode}:normal:{size}:{product_id}:{channel_id}"
                    )
                ),
                **container_kwargs
            )
            await inter.edit_original_message(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True)
            )
            return
        
        # Handler para modo Texto Simples
        if custom_id.startswith("send_mode_text:"):
            parts = custom_id.split(":")
            product_id = parts[3]
            channel_id = int(parts[4]) if len(parts) > 4 else None
            products = db.get_document("loja_products") or {}
            product = products.get(product_id)
            if not product:
                return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado!", ephemeral=True)
            ensure_product_description(product)
            channel = self._resolve_target_channel(inter.guild, channel_id) if channel_id else inter.channel
            if not channel:
                return await inter.response.send_message(f"{emoji.wrong} Canal não encontrado!", ephemeral=True)
            await inter.response.defer()
            msg = await channel.send(
                content=self._build_text_content(product),
                components=self._create_buy_button(product_id),
            )
            product.setdefault("messages", []).append({
                "message_id": msg.id, "channel_id": channel.id, "guild_id": inter.guild.id,
                "mode": "text", "formatted_desc": True, "image_size": "normal",
                "created_at": int(disnake.utils.utcnow().timestamp()),
            })
            products[product_id] = product
            db.save_document("loja_products", products)
            await inter.edit_original_message(
                components=[disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {emoji.correct}\n-# **Produto Publicado com Sucesso!**"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(f"**Modo:** Texto Simples\n**Canal:** {channel.mention}\n**ID da Mensagem:** `{msg.id}`"),
                )],
                flags=disnake.MessageFlags(is_components_v2=True),
            )
            return

        # Handler para modo Legacy básico
        if custom_id.startswith("send_mode_legacy_basic:"):
            parts = custom_id.split(":")
            product_id = parts[3]
            channel_id = int(parts[4]) if len(parts) > 4 else None
            products = db.get_document("loja_products") or {}
            product = products.get(product_id)
            if not product:
                return await inter.response.send_message(f"{emoji.wrong} Produto não encontrado!", ephemeral=True)
            ensure_product_description(product)
            channel = self._resolve_target_channel(inter.guild, channel_id) if channel_id else inter.channel
            if not channel:
                return await inter.response.send_message(f"{emoji.wrong} Canal não encontrado!", ephemeral=True)
            await inter.response.defer()
            msg = await channel.send(
                embed=self._build_basic_legacy_embed(product),
                components=self._create_buy_button(product_id),
            )
            product.setdefault("messages", []).append({
                "message_id": msg.id, "channel_id": channel.id, "guild_id": inter.guild.id,
                "mode": "legacy_basic", "formatted_desc": True, "image_size": "normal",
                "created_at": int(disnake.utils.utcnow().timestamp()),
            })
            products[product_id] = product
            db.save_document("loja_products", products)
            await inter.edit_original_message(
                components=[disnake.ui.Container(
                    disnake.ui.TextDisplay(f"# {emoji.correct}\n-# **Produto Publicado com Sucesso!**"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(f"**Modo:** Legacy\n**Canal:** {channel.mention}\n**ID da Mensagem:** `{msg.id}`"),
                )],
                flags=disnake.MessageFlags(is_components_v2=True),
            )
            return

        # Handler para modo Legacy personalizado
        if custom_id.startswith("send_mode_legacy:"):
            parts = custom_id.split(":")
            desc_format = parts[1]  # formatted ou normal
            size = parts[2]
            product_id = parts[3]
            channel_id = int(parts[4]) if len(parts) > 4 else None
            formatted_desc = (desc_format == "formatted")
            
            # Carregar produto
            products = db.get_document("loja_products")
            product = products.get(product_id)
            
            if not product:
                await inter.response.defer()
                await inter.edit_original_message(
                    content=f"{emoji.wrong} Produto não encontrado!",
                    components=[]
                )
                return
            
            # Obter canal
            channel = self._resolve_target_channel(inter.guild, channel_id) if channel_id else inter.channel
            if not channel:
                await inter.response.defer()
                await inter.edit_original_message(
                    content=f"{emoji.wrong} Canal não encontrado!",
                    components=[]
                )
                return
            
            # Enviar no modo Legacy
            await inter.response.defer()
            embed = self._build_legacy_embed(product, inter.guild, formatted_desc=formatted_desc)
            components = self._create_buy_button(product_id)
            
            try:
                msg = await channel.send(embed=embed, components=components)
            except disnake.HTTPException as e:
                # Se o erro for relacionado a emoji inválido, tentar novamente com emoji.cart
                if e.code == 50035 and "emoji" in str(e).lower():
                    # Recriar botões com emoji.cart como fallback
                    products = db.get_document("loja_products")
                    product = products.get(product_id)
                    info = product.get("info", {}) if product else {}
                    button_config = info.get("buy_button", {})
                    button_label = button_config.get("label", "Comprar")
                    
                    buttons = [
                        disnake.ui.Button(
                            label=button_label,
                            emoji=emoji.cart,
                            style=disnake.ButtonStyle.grey,
                            custom_id=f"buy_product:{product_id}"
                        )
                    ]
                    
                    # Adicionar botão de dúvidas se estiver habilitado
                    doubt_config = db.get_document("loja_doubt_button")
                    if doubt_config.get("enabled") and doubt_config.get("channel_id"):
                        buttons.append(
                            disnake.ui.Button(
                                label=doubt_config.get("button_label", "Dúvidas"),
                                emoji="❓",
                                style=disnake.ButtonStyle.secondary,
                                custom_id="product_doubt_button"
                            )
                        )
                    
                    components = [disnake.ui.ActionRow(*buttons)]
                    msg = await channel.send(embed=embed, components=components)
                else:
                    raise
            
            # Salvar mensagem enviada
            messages = product.get("messages", [])
            messages.append({
                "message_id": msg.id,
                "channel_id": channel.id,
                "guild_id": inter.guild.id,
                "mode": "legacy",
                "formatted_desc": formatted_desc,
                "image_size": size,
                "created_at": int(disnake.utils.utcnow().timestamp())
            })
            
            products[product_id]["messages"] = messages
            db.save_document("loja_products", products)
            
            # Confirmar envio
            colors = db.get_document("custom_colors")
            primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
            container_kwargs = {}
            if primary_color_hex:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
            
            container = disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.correct}\n-# **Produto Publicado com Sucesso!**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"**Modo:** Legacy\n"
                    f"**Canal:** {channel.mention}\n"
                    f"**ID da Mensagem:** `{msg.id}`"
                ),
                **container_kwargs
            )
            
            await inter.edit_original_message(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True)
            )
            return
        
        # Handler para modo Container (Imagem Fora)
        if custom_id.startswith("send_mode_container_outside:"):
            parts = custom_id.split(":")
            desc_format = parts[1]  # formatted ou normal
            size = parts[2]
            product_id = parts[3]
            channel_id = int(parts[4]) if len(parts) > 4 else None
            formatted_desc = (desc_format == "formatted")
            
            # Carregar produto
            products = db.get_document("loja_products")
            product = products.get(product_id)
            
            if not product:
                await inter.response.defer()
                await inter.edit_original_message(
                    content=f"{emoji.wrong} Produto não encontrado!",
                    components=[]
                )
                return
            
            # Obter canal
            channel = self._resolve_target_channel(inter.guild, channel_id) if channel_id else inter.channel
            if not channel:
                await inter.response.defer()
                await inter.edit_original_message(
                    content=f"{emoji.wrong} Canal não encontrado!",
                    components=[]
                )
                return
            
            # Enviar no modo Container (imagem fora)
            await inter.response.defer()
            banner_url = product.get("info", {}).get("banner")
            gallery = None
            files = []
            if banner_url:
                gallery, files = self._build_banner_gallery(banner_url, size)
            wrap_len = None
            if formatted_desc:
                if size == "small":
                    wrap_len = 47
                elif size == "medium":
                    wrap_len = 64
                else:
                    wrap_len = 82
            container_components = self._build_container(product, image_inside=False, product_id=product_id, formatted_desc=formatted_desc, banner_gallery=gallery, wrap_len=wrap_len)
            
            try:
                msg = await channel.send(
                    components=container_components,
                    files=files,
                    flags=disnake.MessageFlags(is_components_v2=True)
                )
            except disnake.HTTPException as e:
                # Se o erro for relacionado a emoji inválido, tentar novamente com emoji.cart
                if e.code == 50035 and "emoji" in str(e).lower():
                    # Reconstruir container com emoji.cart como fallback
                    info = product.get("info", {})
                    button_config = info.get("buy_button", {})
                    button_label = button_config.get("label", "Comprar")
                    
                    # Reconstruir container com emoji seguro
                    container_components = self._build_container(
                        product, 
                        image_inside=False, 
                        product_id=product_id, 
                        formatted_desc=formatted_desc, 
                        banner_gallery=gallery, 
                        wrap_len=wrap_len,
                        force_emoji_cart=True
                    )
                    msg = await channel.send(
                        components=container_components,
                        files=files,
                        flags=disnake.MessageFlags(is_components_v2=True)
                    )
                else:
                    raise
            
            # Salvar mensagem enviada
            messages = product.get("messages", [])
            messages.append({
                "message_id": msg.id,
                "channel_id": channel.id,
                "guild_id": inter.guild.id,
                "mode": "container_outside",
                "formatted_desc": formatted_desc,
                "image_size": size,
                "created_at": int(disnake.utils.utcnow().timestamp())
            })
            
            products[product_id]["messages"] = messages
            db.save_document("loja_products", products)
            
            # Confirmar envio
            colors = db.get_document("custom_colors")
            primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
            container_kwargs = {}
            if primary_color_hex:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
            
            desc_format_text = "Formatada" if formatted_desc else "Normal"
            container = disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.correct}\n-# **Produto Publicado com Sucesso!**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"**Modo:** Container (Imagem Fora)\n"
                    f"**Descrição:** {desc_format_text}\n"
                    f"**Canal:** {channel.mention}\n"
                    f"**ID da Mensagem:** `{msg.id}`"
                ),
                **container_kwargs
            )
            
            await inter.edit_original_message(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True)
            )
            return

        # Handler para modo Container (Imagem Dentro)
        if custom_id.startswith("send_mode_container_inside:"):
            parts = custom_id.split(":")
            desc_format = parts[1]  # formatted ou normal
            size = parts[2]
            product_id = parts[3]
            channel_id = int(parts[4]) if len(parts) > 4 else None
            formatted_desc = (desc_format == "formatted")
            
            # Carregar produto
            products = db.get_document("loja_products")
            product = products.get(product_id)
            
            if not product:
                await inter.response.defer()
                await inter.edit_original_message(
                    content=f"{emoji.wrong} Produto não encontrado!",
                    components=[]
                )
                return
            
            # Obter canal
            channel = self._resolve_target_channel(inter.guild, channel_id) if channel_id else inter.channel
            if not channel:
                await inter.response.defer()
                await inter.edit_original_message(
                    content=f"{emoji.wrong} Canal não encontrado!",
                    components=[]
                )
                return
            
            # Enviar no modo Container (imagem dentro)
            await inter.response.defer()
            banner_url = product.get("info", {}).get("banner")
            gallery = None
            files = []
            if banner_url:
                gallery, files = self._build_banner_gallery(banner_url, size)
            wrap_len = None
            if formatted_desc:
                if size == "small":
                    wrap_len = 47
                elif size == "medium":
                    wrap_len = 64
                else:
                    wrap_len = 82
            container_components = self._build_container(product, image_inside=True, product_id=product_id, formatted_desc=formatted_desc, banner_gallery=gallery, wrap_len=wrap_len)
            
            try:
                msg = await channel.send(
                    components=container_components,
                    files=files,
                    flags=disnake.MessageFlags(is_components_v2=True)
                )
            except disnake.HTTPException as e:
                # Se o erro for relacionado a emoji inválido, tentar novamente com emoji.cart
                if e.code == 50035 and "emoji" in str(e).lower():
                    # Reconstruir container com emoji.cart como fallback
                    info = product.get("info", {})
                    button_config = info.get("buy_button", {})
                    button_label = button_config.get("label", "Comprar")
                    
                    # Reconstruir container com emoji seguro
                    container_components = self._build_container(
                        product, 
                        image_inside=True, 
                        product_id=product_id, 
                        formatted_desc=formatted_desc, 
                        banner_gallery=gallery, 
                        wrap_len=wrap_len,
                        force_emoji_cart=True
                    )
                    msg = await channel.send(
                        components=container_components,
                        files=files,
                        flags=disnake.MessageFlags(is_components_v2=True)
                    )
                else:
                    raise
            
            # Salvar mensagem enviada
            messages = product.get("messages", [])
            messages.append({
                "message_id": msg.id,
                "channel_id": channel.id,
                "guild_id": inter.guild.id,
                "mode": "container_inside",
                "formatted_desc": formatted_desc,
                "image_size": size,
                "created_at": int(disnake.utils.utcnow().timestamp())
            })
            
            products[product_id]["messages"] = messages
            db.save_document("loja_products", products)
            
            # Confirmar envio
            colors = db.get_document("custom_colors")
            primary_color_hex = colors.get("primary") if isinstance(colors, dict) else None
            container_kwargs = {}
            if primary_color_hex:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
            
            desc_format_text = "Formatada" if formatted_desc else "Normal"
            container = disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.correct}\n-# **Produto Publicado com Sucesso!**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"**Modo:** Container (Imagem Dentro)\n"
                    f"**Descrição:** {desc_format_text}\n"
                    f"**Canal:** {channel.mention}\n"
                    f"**ID da Mensagem:** `{msg.id}`"
                ),
                **container_kwargs
            )
            
            await inter.edit_original_message(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True)
            )
            return
    
    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        
        # Handler para seleção de canal
        if custom_id.startswith("select_channel:"):
            product_id = custom_id.split(":", 1)[1]
            # ChannelSelect retorna IDs diretamente, não objetos
            channel_id = int(inter.values[0]) if inter.values else None
            
            if not channel_id:
                await inter.response.send_message(
                    f"{emoji.wrong} Selecione um canal válido!",
                    ephemeral=True
                )
                return
            
            # Mostrar seletor de modo
            await inter.response.defer()
            container = self._build_mode_selector(product_id, str(channel_id))
            await inter.edit_original_message(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True)
            )
            return


def setup(bot: commands.Bot):
    bot.add_cog(SendProduct(bot))
