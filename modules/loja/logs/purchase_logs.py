"""
Sistema de logs de pedidos e eventos de compra
"""
import disnake
from disnake.ext import commands
from datetime import datetime
import io
from typing import Optional, List, Dict, Any
from functions.database import database as db
from functions.emoji import emoji
from functions.utils import utils
from functions.receipt_generator import ReceiptGenerator
import os
import aiohttp


class PurchaseLogsSystem(commands.Cog):
    """Sistema de logs de pedidos e eventos de compra"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.receipt_gen = ReceiptGenerator()
    
    @staticmethod
    def _get_mode_and_color() -> tuple:
        """Retorna o modo de exibição e cor padrão"""
        mode = db.get_document("custom_mode").get("mode", "embed")
        
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        
        color = None
        if primary_color_hex:
            try:
                primary_color = int(primary_color_hex.replace("#", ""), 16)
                color = disnake.Colour(primary_color)
            except:
                pass
        
        return mode, color
    
    @staticmethod
    def _create_stock_file(items: List[str]) -> disnake.File:
        """Cria um arquivo .txt com os itens do estoque"""
        content = "=== ITENS RECEBIDOS ===\n\n"
        for i, item in enumerate(items, 1):
            content += f"{i}. {item}\n"
        
        content += f"\n=== TOTAL: {len(items)} item(s) ===\n"
        content += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        
        file_buffer = io.BytesIO(content.encode('utf-8'))
        file_buffer.seek(0)
        return disnake.File(file_buffer, filename="estoque_recebido.txt")
    
    async def send_order_log(
        self,
        guild: disnake.Guild,
        user: disnake.User,
        product_name: str,
        campo_name: str,
        quantity: int,
        price: float,
        payment_method: str,
        items: Optional[List[str]] = None,
        delivery_type: str = "automatic",
        cart_id: Optional[str] = None
    ):
        """Envia log detalhado do pedido para o canal de logs de pedidos"""
        try:
            # Obter canal de logs
            canais = db.get_document("canais") or {}
            log_channel_id = canais.get("canal_de_logs_de_pedidos")
            
            if not log_channel_id:
                print(f"[LOG PEDIDOS] Canal de logs de pedidos não configurado")
                return
            
            try:
                channel = guild.get_channel(int(log_channel_id))
            except (ValueError, TypeError) as e:
                print(f"[LOG PEDIDOS] Erro ao converter channel_id: {log_channel_id} - {e}")
                return
            
            if not channel:
                print(f"[LOG PEDIDOS] Canal {log_channel_id} não encontrado no servidor")
                return
            
            mode, color = self._get_mode_and_color()
            
            # Formatar método de pagamento
            payment_methods_map = {
                "pix": "PIX",
                "card": "Cartão de Crédito",
                "crypto": "Criptomoeda"
            }
            payment_display = payment_methods_map.get(payment_method, payment_method.upper())
            
            # Formatar preço
            price_display = utils.format_price_brl(price)
            
            # Preparar arquivo de estoque se necessário
            stock_file = None
            stock_text = None
            
            # Validar se items é uma lista
            if items and isinstance(items, list) and len(items) > 0:
                items_text = "\n".join([f"`{i+1}.` {item}" for i, item in enumerate(items)])
                if len(items_text) > 2000:
                    stock_file = self._create_stock_file(items)
                    stock_text = f"*Arquivo anexado com {len(items)} item(s)*"
                else:
                    stock_text = items_text
            
            if mode == "embed":
                # Criar embed
                embed = disnake.Embed(
                    title=f"{emoji.z0}\n-# Novo Pedido Realizado",
                    description=(
                        f"**Cliente:** {user.mention} (`{user.id}`)\n"
                        f"**Produto:** {product_name}\n"
                        f"**Opção:** {campo_name}\n"
                        f"**Quantidade:** {quantity}\n"
                        f"**Valor:** {price_display}\n"
                        f"**Método:** {payment_display}\n"
                        f"**Tipo de Entrega:** {'Manual' if delivery_type == 'manual' else 'Automática'}\n"
                        f"**ID do Pedido:** `{cart_id or 'N/A'}`"
                    ),
                    color=color or disnake.Color.green(),
                    timestamp=datetime.now()
                )
                
                embed.set_footer(
                    text=f"Pedido processado • {guild.name}",
                    icon_url=guild.icon.url if guild.icon else None
                )
                
                # Enviar mensagem do log primeiro
                log_message = await channel.send(embed=embed)
                
                # Se houver estoque entregue, sempre enviar arquivo .txt como resposta ao log
                if items and log_message:
                    try:
                        stock_file_reply = self._create_stock_file(items)
                        await log_message.reply(f"{emoji.cardbox} **Estoque Entregue:**", file=stock_file_reply)
                    except Exception as e:
                        print(f"[LOG PEDIDOS] Erro ao enviar resposta com estoque: {e}")
                
                print(f"[LOG PEDIDOS] Log enviado com sucesso para {channel.name} (embed)")
            
            else:
                # Criar container
                container_kwargs = {}
                if color:
                    container_kwargs["accent_colour"] = color
                
                # Construir lista de componentes do container (sem None)
                container_children = [
                    disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Novo Pedido Realizado"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(f"## {emoji.member} Cliente\n-# {user.mention} (`{user.id}`)"),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        f"## {emoji.bag} Produto\n"
                        f"-# **Nome:** {product_name}\n"
                        f"-# **Opção:** {campo_name}\n"
                        f"-# **Quantidade:** `{quantity}`"
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        f"## {emoji.dollar} Pagamento\n"
                        f"-# **Valor:** `{price_display}`\n"
                        f"-# **Método:** {payment_display}"
                    ),
                    disnake.ui.Separator(),
                    disnake.ui.TextDisplay(
                        f"## {emoji.truck if delivery_type == 'manual' else emoji.correct} Entrega\n"
                        f"-# **Tipo:** {'Manual' if delivery_type == 'manual' else 'Automática'}\n"
                        f"-# **ID do Pedido:** `{cart_id or 'N/A'}`"
                    )
                ]
                
                components = [
                    disnake.ui.Container(
                        *container_children,
                        **container_kwargs
                    )
                ]
                
                # Enviar mensagem do log primeiro
                log_message = await channel.send(
                    components=components,
                    flags=disnake.MessageFlags(is_components_v2=True)
                )
                
                # Se houver estoque entregue, sempre enviar arquivo .txt como resposta ao log
                if items and log_message:
                    try:
                        stock_file_reply = self._create_stock_file(items)
                        await log_message.reply(f"{emoji.cardbox} **Estoque Entregue:**", file=stock_file_reply)
                    except Exception as e:
                        print(f"[LOG PEDIDOS] Erro ao enviar resposta com estoque: {e}")
                
                print(f"[LOG PEDIDOS] Log enviado com sucesso para {channel.name} (container)")
        
        except Exception as e:
            print(f"[LOG EVENTO] ERRO GERAL ao enviar evento de compra: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_cart_created_log(
        self,
        guild: disnake.Guild,
        user: disnake.User,
        product_name: str,
        campo_name: str,
        quantity: int,
        price: float,
        payment_method: str,
        cart_url: str,
        cart_id: str
    ):
        """Envia log de criação de carrinho"""
        try:
            # Obter canal de logs
            canais = db.get_document("canais") or {}
            log_channel_id = canais.get("canal_de_logs_de_pedidos")
            
            if not log_channel_id:
                print(f"[LOG CARRINHO] Canal de logs de pedidos não configurado")
                return
            
            try:
                channel = guild.get_channel(int(log_channel_id))
            except (ValueError, TypeError) as e:
                print(f"[LOG CARRINHO] Erro ao converter channel_id: {log_channel_id} - {e}")
                return
            
            if not channel:
                print(f"[LOG CARRINHO] Canal {log_channel_id} não encontrado no servidor")
                return
            
            mode, color = self._get_mode_and_color()
            
            # Formatar método de pagamento
            payment_methods_map = {
                "pix": "PIX",
                "pix_manual": "PIX Manual",
                "card": "Cartão de Crédito",
                "crypto": "Criptomoeda",
                "mercado_pago": "Mercado Pago",
                "stripe": "Stripe",
                "paypal": "PayPal"
            }
            payment_display = payment_methods_map.get(payment_method, payment_method.upper())
            
            # Formatar preço
            price_display = utils.format_price_brl(price)
            
            if mode == "embed":
                embed = disnake.Embed(
                    title=f"Carrinho Criado",
                    description=(
                        f"**Cliente:** {user.mention} (`{user.id}`)\n"
                        f"**Produto:** {product_name}\n"
                        f"**Opção:** {campo_name}\n"
                        f"**Quantidade:** {quantity}\n"
                        f"**Valor:** {price_display}\n"
                        f"**Método:** {payment_display}\n"
                        f"**Status:** Aguardando Pagamento"
                    ),
                    color=disnake.Color.blue(),
                    timestamp=datetime.now()
                )
                
                embed.set_footer(
                    text=f"ID: {cart_id} • {guild.name}",
                    icon_url=guild.icon.url if guild.icon else None
                )
                
                components = [
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Abrir Carrinho",
                            style=disnake.ButtonStyle.link,
                            url=cart_url,
                            emoji=emoji.cart
                        )
                    )
                ]
                
                await channel.send(embed=embed, components=components)
                print(f"[LOG CARRINHO] Log de carrinho criado enviado para {channel.name} (embed)")
            
            else:
                container_kwargs = {}
                if color:
                    container_kwargs["accent_colour"] = color
                
                components = [
                    disnake.ui.Container(
                        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Carrinho Criado"),
                        disnake.ui.Separator(),
                        disnake.ui.TextDisplay(
                            f"**Cliente:** {user.mention}\n"
                            f"**Produto:** {product_name}\n"
                            f"**Opção:** {campo_name}\n"
                            f"**Quantidade:** `{quantity}`\n"
                            f"**Valor:** `{price_display}`\n"
                            f"**Método:** {payment_display}\n"
                            f"**Status:** Aguardando Pagamento"
                        ),
                        **container_kwargs
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Abrir Carrinho",
                            style=disnake.ButtonStyle.link,
                            url=cart_url,
                            emoji=emoji.cart
                        )
                    )
                ]
                
                await channel.send(
                    components=components,
                    flags=disnake.MessageFlags(is_components_v2=True)
                )
                print(f"[LOG CARRINHO] Log de carrinho criado enviado para {channel.name} (container)")
        
        except Exception as e:
            print(f"[LOG CARRINHO] Erro ao enviar log de carrinho criado: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_purchase_event(
        self,
        guild: disnake.Guild,
        user: disnake.User,
        product_name: str,
        campo_name: str,
        quantity: int,
        price: float,
        product_id: str,
        original_price: float = None,
        discount_amount: float = None,
        coupon_code: str = None
    ):
        """Envia evento público de compra como imagem"""
        print(f"[LOG EVENTO] ✅ Iniciando send_purchase_event para {user.name}")
        try:
            # Obter canal de eventos
            canais = db.get_document("canais") or {}
            event_channel_id = canais.get("canal_de_evento_de_compras")
            print(f"[LOG EVENTO] event_channel_id: {event_channel_id}")
            
            if not event_channel_id:
                print(f"[LOG EVENTO] Canal de evento de compras não configurado")
                return
            
            try:
                channel = guild.get_channel(int(event_channel_id))
                print(f"[LOG EVENTO] Canal encontrado: {channel}")
            except (ValueError, TypeError) as e:
                print(f"[LOG EVENTO] Erro ao converter channel_id: {event_channel_id} - {e}")
                return
            
            if not channel:
                print(f"[LOG EVENTO] Canal {event_channel_id} não encontrado no servidor")
                return
            
            print(f"[LOG EVENTO] Prosseguindo com download de avatar e ícone")
            
            # Obter informações do produto para criar link
            products = db.get_document("loja_products") or {}
            product = products.get(product_id, {})
            
            # Buscar mensagem do produto na estrutura messages (array)
            product_url = None
            product_messages = product.get("messages", [])
            if product_messages:
                latest_message = max(product_messages, key=lambda m: m.get("created_at", 0))
                product_channel_id = latest_message.get("channel_id")
                product_message_id = latest_message.get("message_id")
                if product_channel_id and product_message_id:
                    product_url = f"https://discord.com/channels/{guild.id}/{product_channel_id}/{product_message_id}"

            # Baixar avatar do usuário e ícone do servidor temporariamente
            avatar_path = f"temp_avatar_{user.id}.png"
            icon_path = f"temp_icon_{guild.id}.png"
            
            async with aiohttp.ClientSession() as session:
                # Avatar do usuário
                try:
                    async with session.get(str(user.display_avatar.url)) as resp:
                        if resp.status == 200:
                            with open(avatar_path, "wb") as f:
                                f.write(await resp.read())
                except Exception as e:
                    print(f"[LOG EVENTO] Erro ao baixar avatar: {e}")
                    avatar_path = None
                
                # Ícone do servidor
                try:
                    if guild.icon:
                        async with session.get(str(guild.icon.url)) as resp:
                            if resp.status == 200:
                                with open(icon_path, "wb") as f:
                                    f.write(await resp.read())
                    else:
                        icon_path = None
                except Exception as e:
                    print(f"[LOG EVENTO] Erro ao baixar ícone do servidor: {e}")
                    icon_path = None

            # Gerar a imagem do recibo
            print(f"[LOG EVENTO] Gerando recibo com desconto: {discount_amount}, cupom: {coupon_code}")
            receipt_buffer = self.receipt_gen.generate_receipt(
                user_name=user.display_name,
                user_handle=user.name,
                user_avatar_path=avatar_path,
                product_name=f"{product_name} | {campo_name}",
                quantity=quantity,
                price=price,
                guild_name=guild.name,
                guild_icon_path=icon_path,
                footer_text="ZYNEX Systems",
                original_price=original_price,
                discount_amount=discount_amount,
                coupon_code=coupon_code
            )
            
            file = disnake.File(receipt_buffer, filename="receita.png")
            print(f"[LOG EVENTO] Arquivo de recibo criado com sucesso")
            
            # Componentes (botão de comprar também)
            components = []
            if product_url:
                components = [
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Comprar Também",
                            style=disnake.ButtonStyle.link,
                            url=product_url
                        )
                    )
                ]
                print(f"[LOG EVENTO] Botão de compra adicionado")

            await channel.send(file=file, components=components if components else None)
            print(f"[LOG EVENTO] Evento de compra enviado como imagem para {channel.name}")
        
        except Exception as e:
            print(f"[LOG EVENTO] ERRO ao enviar evento de compra: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Limpar arquivos temporários
            try:
                if avatar_path and os.path.exists(avatar_path):
                    os.remove(avatar_path)
                if icon_path and os.path.exists(icon_path):
                    os.remove(icon_path)
            except:
                pass


    async def send_purchase_event_bulk(
        self,
        guild: disnake.Guild,
        user: disnake.User,
        items: list,  # Lista de itens: [{product_name, campo_name, quantity, price, product_id}, ...]
        total_price: float,
        subtotal: float = None,
        discount_amount: float = None,
        coupon_code: str = None
    ):
        """Envia evento público de compra como uma única imagem com todos os itens"""
        print(f"[LOG EVENTO] ✅ Iniciando send_purchase_event_bulk para {user.name} com {len(items)} itens")
        try:
            # Obter canal de eventos
            canais = db.get_document("canais") or {}
            event_channel_id = canais.get("canal_de_evento_de_compras")
            print(f"[LOG EVENTO] event_channel_id: {event_channel_id}")
            
            if not event_channel_id:
                print(f"[LOG EVENTO] Canal de evento de compras não configurado")
                return
            
            try:
                channel = guild.get_channel(int(event_channel_id))
                print(f"[LOG EVENTO] Canal encontrado: {channel}")
            except (ValueError, TypeError) as e:
                print(f"[LOG EVENTO] Erro ao converter channel_id: {event_channel_id} - {e}")
                return
            
            if not channel:
                print(f"[LOG EVENTO] Canal {event_channel_id} não encontrado no servidor")
                return
            
            print(f"[LOG EVENTO] Prosseguindo com download de avatar e ícone")
            
            # Baixar avatar do usuário e ícone do servidor temporariamente
            avatar_path = f"temp_avatar_{user.id}.png"
            icon_path = f"temp_icon_{guild.id}.png"
            
            async with aiohttp.ClientSession() as session:
                # Avatar do usuário
                try:
                    async with session.get(str(user.display_avatar.url)) as resp:
                        if resp.status == 200:
                            with open(avatar_path, "wb") as f:
                                f.write(await resp.read())
                except Exception as e:
                    print(f"[LOG EVENTO] Erro ao baixar avatar: {e}")
                    avatar_path = None
                
                # Ícone do servidor
                try:
                    if guild.icon:
                        async with session.get(str(guild.icon.url)) as resp:
                            if resp.status == 200:
                                with open(icon_path, "wb") as f:
                                    f.write(await resp.read())
                    else:
                        icon_path = None
                except Exception as e:
                    print(f"[LOG EVENTO] Erro ao baixar ícone do servidor: {e}")
                    icon_path = None

            # Gerar a imagem do recibo com todos os itens
            print(f"[LOG EVENTO] Gerando recibo com {len(items)} itens, desconto: {discount_amount}, cupom: {coupon_code}")
            receipt_buffer = self.receipt_gen.generate_receipt(
                user_name=user.display_name,
                user_handle=user.name,
                user_avatar_path=avatar_path,
                items=items,
                total_price=total_price,
                guild_name=guild.name,
                guild_icon_path=icon_path,
                footer_text="ZYNEX Systems",
                subtotal=subtotal,
                discount_amount=discount_amount,
                coupon_code=coupon_code
            )
            
            file = disnake.File(receipt_buffer, filename="receita.png")
            print(f"[LOG EVENTO] Arquivo de recibo criado com sucesso")
            
            # Componentes (botão de comprar também) - usar o primeiro produto como referência
            components = []
            if items:
                products = db.get_document("loja_products") or {}
                first_item = items[0]
                product_id = first_item.get("product_id")
                product = products.get(product_id, {})
                
                # Buscar mensagem do produto na estrutura messages (array)
                product_url = None
                product_messages = product.get("messages", [])
                if product_messages:
                    latest_message = max(product_messages, key=lambda m: m.get("created_at", 0))
                    product_channel_id = latest_message.get("channel_id")
                    product_message_id = latest_message.get("message_id")
                    if product_channel_id and product_message_id:
                        product_url = f"https://discord.com/channels/{guild.id}/{product_channel_id}/{product_message_id}"
                
                if product_url:
                    components = [
                        disnake.ui.ActionRow(
                            disnake.ui.Button(
                                label="Comprar Também",
                                style=disnake.ButtonStyle.link,
                                url=product_url
                            )
                        )
                    ]
                    print(f"[LOG EVENTO] Botão de compra adicionado")

            await channel.send(file=file, components=components if components else None)
            print(f"[LOG EVENTO] Evento de compra enviado como imagem para {channel.name}")
        
        except Exception as e:
            print(f"[LOG EVENTO] ERRO ao enviar evento de compra bulk: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Limpar arquivos temporários
            try:
                if avatar_path and os.path.exists(avatar_path):
                    os.remove(avatar_path)
                if icon_path and os.path.exists(icon_path):
                    os.remove(icon_path)
            except:
                pass


def setup(bot: commands.Bot):
    bot.add_cog(PurchaseLogsSystem(bot))
