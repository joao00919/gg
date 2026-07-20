"""
Sistema de gerenciamento de estoque centralizado
"""
import asyncio
import sys
from typing import Optional, List, Dict
import disnake
from functions.database import database as db
from functions.emoji import emoji

KEY_ESTOQUE = "database/loja/estoque.json"


class StockManager:
    """Gerencia o estoque de produtos"""
    
    @staticmethod
    def _load_stock() -> dict:
        """Carrega o estoque do arquivo JSON local"""
        stock = db.obter(KEY_ESTOQUE) or {}
        return stock
    
    @staticmethod
    def _save_stock(stock_data: dict):
        """Salva o estoque no arquivo JSON local"""
        db.salvar(KEY_ESTOQUE, stock_data)
    
    @staticmethod
    def get_available_stock(product_id: str, campo_id: str) -> int:
        """Retorna a quantidade disponível em estoque"""
        # Verificar se é estoque infinito
        products = db.get_document("loja_products") or {}
        product = products.get(product_id, {})
        campo = product.get("campos", {}).get(campo_id, {})
        
        if campo.get("infinite_stock", {}).get("enabled"):
            return 999999  
            # Retorna numero grande
        
        stock = StockManager._load_stock()
        product_stock = stock.get(product_id, {})
        campo_stock = product_stock.get(campo_id, [])
        count = len(campo_stock) if isinstance(campo_stock, list) else 0
        return count
    
    @staticmethod
    def get_stock_items(product_id: str, campo_id: str, quantity: int) -> Optional[List[str]]:
        """
        Retira itens do estoque e retorna a lista de itens.
        Retorna None se não houver estoque suficiente.
        """
        # Verificar se é estoque infinito
        products = db.get_document("loja_products") or {}
        product = products.get(product_id, {})
        campo = product.get("campos", {}).get(campo_id, {})
        
        infinite_stock = campo.get("infinite_stock", {})
        if infinite_stock.get("enabled"):
            # Retornar o valor infinito repetido pela quantidade solicitada
            value = infinite_stock.get("value", "Item de estoque infinito")
            return [value] * quantity
        
        stock = StockManager._load_stock()
        
        # Garantir estrutura
        if product_id not in stock:
            stock[product_id] = {}
        if campo_id not in stock[product_id]:
            stock[product_id][campo_id] = []
        
        campo_stock = stock[product_id][campo_id]
        
        if not isinstance(campo_stock, list):
            return None
        
        if len(campo_stock) < quantity:
            return None
        
        # Retirar itens
        items = campo_stock[:quantity]
        stock[product_id][campo_id] = campo_stock[quantity:]
        
        # Salvar
        StockManager._save_stock(stock)
        
        return items
    
    @staticmethod
    def add_stock_items(product_id: str, campo_id: str, items: List[str]):
        """Adiciona itens ao estoque e notifica usuários se necessário"""
        stock = StockManager._load_stock()
        
        # Verificar se havia estoque antes (para notificações)
        had_stock = False
        if product_id in stock and campo_id in stock[product_id]:
            existing_stock = stock[product_id][campo_id]
            if isinstance(existing_stock, list):
                had_stock = len(existing_stock) > 0
            elif isinstance(existing_stock, dict):
                had_stock = bool(existing_stock)
        
        # Garantir estrutura
        if product_id not in stock:
            stock[product_id] = {}
        if campo_id not in stock[product_id]:
            stock[product_id][campo_id] = []
        
        # Adicionar itens
        if isinstance(stock[product_id][campo_id], list):
            stock[product_id][campo_id].extend(items)
        else:
            stock[product_id][campo_id] = items
        
        # Salvar
        StockManager._save_stock(stock)
        
        # Se não havia estoque antes e agora há, criar tarefa para notificar usuários
        # A notificação será feita assincronamente pelo código que chama add_stock_items
        if not had_stock and len(items) > 0:
            # Retornar flag indicando que precisa notificar
            return True
        return False
    
    @staticmethod
    def return_stock_items(product_id: str, campo_id: str, items: List[str]):
        """Devolve itens ao estoque (em caso de cancelamento)"""
        StockManager.add_stock_items(product_id, campo_id, items)
    
    @staticmethod
    def sync_from_products():
        """
        Sincroniza o estoque do products.json para estoque.json
        Usado para migração inicial
        """
        products = db.obter("database/loja/products.json") or {}
        stock = StockManager._load_stock()
        
        for product_id, product in products.items():
            campos = product.get("campos", {})
            
            for campo_id, campo in campos.items():
                # Pegar estoque da opção
                campo_stock = campo.get("stock", [])
                
                if isinstance(campo_stock, list) and campo_stock:
                    # Garantir estrutura
                    if product_id not in stock:
                        stock[product_id] = {}
                    
                    # Se não existe no estoque centralizado, copiar
                    if campo_id not in stock[product_id]:
                        stock[product_id][campo_id] = campo_stock.copy()
        
        # Salvar estoque centralizado
        StockManager._save_stock(stock)
        return stock
    
    @staticmethod
    def get_all_stock() -> dict:
        """Retorna todo o estoque"""
        return StockManager._load_stock()
    
    @staticmethod
    async def _notify_stock_available(product_id: str, campo_id: str, bot=None):
        """Notifica usuários que estão aguardando estoque"""
        if not bot:
            return
        
        products = db.get_document("loja_products")
        product = products.get(product_id, {})
        
        if not product:
            return
        
        # Obter notificações do novo sistema
        notifications_doc = db.get_document("loja_stock_notifications") or {}
        notifications = notifications_doc.get("notifications", {})
        
        # Filtrar notificações para este produto e campo que ainda não foram notificadas
        to_notify = []
        for key, notification_data in notifications.items():
            if (notification_data.get("product_id") == product_id and 
                notification_data.get("campo_id") == campo_id and 
                not notification_data.get("notified", False)):
                to_notify.append(key)
        
        if not to_notify:
            return
        
        product_name = product.get("name", "Produto")
        campos = product.get("campos", {})
        campo = campos.get(campo_id, {})
        campo_name = campo.get("name", campo_id)
        
        # Preparar mensagem de notificação
        color_data = db.get_document("custom_colors") or {}
        primary_color_hex = color_data.get("primary")
        mode = db.get_document("custom_mode").get("mode")
        
        # Obter URL da mensagem do produto (se existir)
        # Priorizar mensagens armazenadas no produto
        product_message_id = None
        product_channel_id = None
        product_guild_id = None
        
        # Tentar encontrar mensagem do produto usando dados armazenados
        product_messages = product.get("messages", [])
        if product_messages:
            # Pegar a mensagem mais recente
            latest_message = max(product_messages, key=lambda m: m.get("created_at", 0))
            product_message_id = latest_message.get("message_id")
            product_channel_id = latest_message.get("channel_id")
            product_guild_id = latest_message.get("guild_id")
        
        # Se não encontrou nos dados armazenados, buscar manualmente
        if not product_message_id:
            for guild in bot.guilds:
                for channel in guild.channels:
                    if isinstance(channel, disnake.TextChannel):
                        try:
                            # Buscar mensagens mais recentes primeiro
                            async for message in channel.history(limit=100):
                                if message.author == bot.user and message.components:
                                    for row in message.components:
                                        if row.children:
                                            for component in row.children:
                                                if isinstance(component, disnake.ui.Button):
                                                    if component.custom_id and component.custom_id.startswith(f"buy_product:{product_id}"):
                                                        product_message_id = message.id
                                                        product_channel_id = channel.id
                                                        product_guild_id = guild.id
                                                        break
                                            if product_message_id:
                                                break
                                        if product_message_id:
                                            break
                                    if product_message_id:
                                        break
                                if product_message_id:
                                    break
                        except (disnake.Forbidden, disnake.HTTPException):
                            continue
                        except Exception:
                            continue
                    if product_message_id:
                        break
                if product_message_id:
                    break
        
        notified_users = []
        failed_users = []
        
        for notification_key in to_notify:
            notification_data = notifications[notification_key]
            user_id_str = notification_data.get("user_id")
            
            if not user_id_str:
                continue
            
            try:
                user_id = int(user_id_str)
                user = await bot.fetch_user(user_id)
                
                # Criar link para o produto (se temos message_id e channel_id)
                product_link = None
                if product_message_id and product_channel_id and product_guild_id:
                    try:
                        guild = bot.get_guild(product_guild_id)
                        if guild:
                            channel = guild.get_channel(product_channel_id)
                            if channel:
                                message = await channel.fetch_message(product_message_id)
                                product_link = message.jump_url
                    except:
                        pass
                
                # Mensagem com mention do usuário
                message_content = f"Olá {user.mention}, a opção **{campo_name}** do produto **{product_name}** acabou de receber reestoque!"
                
                # Criar botões
                buttons = []
                
                # Botão de link para o produto (se temos link)
                if product_link:
                    buttons.append(
                        disnake.ui.Button(
                            label="Ver Produto",
                            emoji=emoji.cart,
                            style=disnake.ButtonStyle.link,
                            url=product_link
                        )
                    )
                
                # Botão para desativar notificação
                buttons.append(
                    disnake.ui.Button(
                        label="Desativar Notificação",
                        emoji=emoji.off,
                        style=disnake.ButtonStyle.red,
                        custom_id=f"disable_stock_notification:{product_id}:{campo_id}"
                    )
                )
                
                if mode == "embed":
                    embed_kwargs = {}
                    if primary_color_hex:
                        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)
                    embed = disnake.Embed(
                        title="{emoji.warn} Estoque Disponível!",
                        description=message_content,
                        **embed_kwargs
                    )
                    
                    if buttons:
                        components = [disnake.ui.ActionRow(*buttons)]
                        await user.send(embed=embed, components=components)
                    else:
                        await user.send(embed=embed)
                else:
                    container_kwargs = {}
                    if primary_color_hex:
                        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
                    
                    container_items = [
                        disnake.ui.TextDisplay(f"# {emoji.warn}\n-# **Estoque Disponível!**\n\n{message_content}")
                    ]
                    
                    container = disnake.ui.Container(
                        *container_items,
                        **container_kwargs
                    )
                    
                    if buttons:
                        components = [container, disnake.ui.ActionRow(*buttons)]
                        await user.send(
                            components=components,
                            flags=disnake.MessageFlags(is_components_v2=True)
                        )
                    else:
                        await user.send(
                            components=[container],
                            flags=disnake.MessageFlags(is_components_v2=True)
                        )
                
                # Marcar como notificado
                notification_data["notified"] = True
                notification_data["notified_at"] = int(disnake.utils.utcnow().timestamp())
                notifications[notification_key] = notification_data
                notified_users.append(notification_key)
                
            except disnake.Forbidden:
                # Usuário bloqueou DMs - remover notificação
                failed_users.append(notification_key)
                del notifications[notification_key]
            except disnake.NotFound:
                # Usuário não encontrado - remover notificação
                failed_users.append(notification_key)
                del notifications[notification_key]
            except Exception as e:
                # Outro erro - manter notificação mas logar erro
                failed_users.append(notification_key)
        
        # Atualizar notificações
        notifications_doc["notifications"] = notifications
        db.save_document("loja_stock_notifications", notifications_doc)
    
