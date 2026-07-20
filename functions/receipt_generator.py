import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import io
from typing import List, Dict, Optional

class ReceiptGenerator:
    def __init__(self):
        # Caminho relativo à raiz do projeto
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.fonts_path = os.path.join(self.base_dir, "assets", "fonts")
        
        self.fonts = {
            "regular": os.path.join(self.fonts_path, "gg sans Regular.ttf"),
            "medium": os.path.join(self.fonts_path, "gg sans Medium.ttf"),
            "semibold": os.path.join(self.fonts_path, "gg sans Semibold.ttf"),
            "bold": os.path.join(self.fonts_path, "gg sans Bold.ttf")
        }
        
        self.bg_color = (18, 18, 18)
        self.card_color = (24, 24, 24)
        self.text_color = (255, 255, 255)
        self.subtext_color = (180, 180, 180)
        self.green_color = (87, 242, 135)
        self.footer_color = (100, 100, 100)

    def generate_receipt(
        self,
        user_name: str,
        user_handle: str,
        user_avatar_path: str,
        items: List[Dict],  # Lista de itens: [{product_name, campo_name, quantity, price}, ...]
        total_price: float,
        guild_name: str,
        guild_icon_path: str = None,
        footer_text: str = "ZYNEX Systems",
        subtotal: float = None,
        discount_amount: float = None,
        coupon_code: str = None
    ) -> io.BytesIO:
        width = 800
        base_height = 500
        
        # Calcular altura dinâmica baseada no número de itens
        item_height = 35  # Altura por item
        items_section_height = len(items) * item_height + 40  # +40 para espaçamento
        
        # Adicionar altura para desconto e cupom
        extra_height = 0
        if discount_amount and discount_amount > 0:
            extra_height += 40
            if coupon_code:
                extra_height += 35
        
        height = base_height + items_section_height + extra_height
        img = Image.new('RGB', (width, height), self.bg_color)
        draw = ImageDraw.Draw(img)

        padding = 40
        card_coords = [padding, padding, width - padding, height - padding]
        draw.rounded_rectangle(card_coords, radius=30, fill=self.card_color)

        # Carregar fontes com fallback
        try:
            font_title = ImageFont.truetype(self.fonts["bold"], 36)
            font_name = ImageFont.truetype(self.fonts["bold"], 28)
            font_handle = ImageFont.truetype(self.fonts["regular"], 20)
            font_date = ImageFont.truetype(self.fonts["regular"], 18)
            font_label = ImageFont.truetype(self.fonts["semibold"], 22)
            font_item = ImageFont.truetype(self.fonts["regular"], 20)
            font_price = ImageFont.truetype(self.fonts["bold"], 20)
            font_total_label = ImageFont.truetype(self.fonts["regular"], 28)
            font_total_value = ImageFont.truetype(self.fonts["bold"], 36)
            font_footer = ImageFont.truetype(self.fonts["regular"], 16)
        except Exception:
            font_title = font_name = font_handle = font_date = font_label = font_item = font_price = font_total_label = font_total_value = font_footer = ImageFont.load_default()

        # Avatar do Usuário
        avatar_size = 80
        avatar_x, avatar_y = padding + 30, padding + 30
        
        if user_avatar_path and os.path.exists(user_avatar_path):
            try:
                avatar = Image.open(user_avatar_path).convert("RGBA")
                avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                mask = Image.new('L', (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                img.paste(avatar, (avatar_x, avatar_y), mask)
            except Exception:
                draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(50, 50, 50))
        else:
            draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(50, 50, 50))

        # Nome e handle do usuário
        draw.text((avatar_x + avatar_size + 20, avatar_y + 10), user_name, font=font_name, fill=self.text_color)
        draw.text((avatar_x + avatar_size + 20, avatar_y + 45), f"@{user_handle}", font=font_handle, fill=self.subtext_color)

        # Data (canto superior direito)
        now = datetime.now()
        date_str = now.strftime("%d/%m • %H:%M")
        date_w = draw.textbbox((0, 0), date_str, font=font_date)[2]
        draw.text((width - padding - 30 - date_w, avatar_y + 15), date_str, font=font_date, fill=self.subtext_color)

        # Status (check + "Compra Realizada")
        check_y = avatar_y + avatar_size + 30
        draw.ellipse([avatar_x, check_y, avatar_x + 30, check_y + 30], fill=self.green_color)
        draw.line([avatar_x + 8, check_y + 15, avatar_x + 14, check_y + 21], fill=(0, 0, 0), width=3)
        draw.line([avatar_x + 14, check_y + 21, avatar_x + 22, check_y + 9], fill=(0, 0, 0), width=3)
        draw.text((avatar_x + 45, check_y - 5), "Compra Realizada", font=font_title, fill=self.text_color)

        # Carrinho (seção)
        cart_y = check_y + 60
        draw.text((avatar_x, cart_y), "Carrinho", font=font_label, fill=self.subtext_color)
        
        # Listar itens
        current_y = cart_y + 40
        for item in items:
            product_name = item.get("product_name", "Produto")
            campo_name = item.get("campo_name", "")
            quantity = item.get("quantity", 1)
            price = item.get("price", 0)
            
            item_text = f"{quantity}x {product_name} | {campo_name}"
            price_text = f"R$ {price:.2f}".replace(".", ",")
            
            draw.text((avatar_x, current_y), item_text, font=font_item, fill=self.text_color)
            price_w = draw.textbbox((0, 0), price_text, font=font_price)[2]
            draw.text((width - padding - 30 - price_w, current_y), price_text, font=font_price, fill=self.text_color)
            
            current_y += item_height

        # Subtotal
        current_y += 10
        if subtotal:
            subtotal_text = f"R$ {subtotal:.2f}".replace(".", ",")
            draw.text((avatar_x, current_y), "Subtotal", font=font_label, fill=self.subtext_color)
            subtotal_w = draw.textbbox((0, 0), subtotal_text, font=font_price)[2]
            draw.text((width - padding - 30 - subtotal_w, current_y), subtotal_text, font=font_price, fill=self.subtext_color)
            current_y += 40

        # Desconto e cupom
        if discount_amount and discount_amount > 0:
            discount_text = f"Desconto: -R$ {discount_amount:.2f}".replace(".", ",")
            draw.text((avatar_x, current_y), discount_text, font=font_label, fill=self.green_color)
            current_y += 40
            
            if coupon_code:
                coupon_text = f"Cupom: {coupon_code}"
                draw.text((avatar_x, current_y), coupon_text, font=font_handle, fill=self.subtext_color)
                current_y += 35

        # Separador
        sep_y = current_y + 10
        draw.line([avatar_x, sep_y, width - padding - 30, sep_y], fill=(40, 40, 40), width=2)

        # Total
        total_y = sep_y + 40
        draw.text((avatar_x, total_y), "Valor pago", font=font_total_label, fill=self.text_color)
        total_price_text = f"R$ {total_price:.2f}".replace(".", ",")
        total_w = draw.textbbox((0, 0), total_price_text, font=font_total_value)[2]
        draw.text((width - padding - 30 - total_w, total_y - 5), total_price_text, font=font_total_value, fill=self.green_color)

        # Footer (Dinâmico)
        footer_y = height - padding - 40
        icon_size = 30
        
        # Ícone do Servidor
        if guild_icon_path and os.path.exists(guild_icon_path):
            try:
                g_icon = Image.open(guild_icon_path).convert("RGBA")
                g_icon = g_icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                img.paste(g_icon, (avatar_x, footer_y), g_icon)
            except Exception:
                draw.rectangle([avatar_x, footer_y, avatar_x + icon_size, footer_y + icon_size], fill=(50, 50, 50))
        else:
            draw.rectangle([avatar_x, footer_y, avatar_x + icon_size, footer_y + icon_size], fill=(50, 50, 50))
            
        # Nome do Servidor (Dinâmico)
        draw.text((avatar_x + 40, footer_y + 5), guild_name.upper(), font=font_footer, fill=self.text_color)
        
        # Site no Rodapé
        footer_site_w = draw.textbbox((0, 0), footer_text, font=font_footer)[2]
        draw.text((width - padding - 30 - footer_site_w, footer_y + 5), footer_text, font=font_footer, fill=self.footer_color)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
