import disnake
import asyncio
import base64
import io
import aiohttp
import time
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from functions.database import database as db
from functions.emoji import emoji
from functions.message import message
from functions.text_utils import wrap_text
from functions.utils import utils

# Cache simples para métodos de pagamento (TTL de 30 segundos)
_payment_methods_cache = {"data": None, "timestamp": 0, "ttl": 30}
from functions.payments import (
    create_mp_payment_from_settings,
    create_mp_site_payment_from_settings,
    create_efi_payment_from_settings,
    create_stripe_payment_from_settings,
    create_coinbase_payment_from_settings,
    create_asaas_pix_payment_from_settings,
    create_manual_pix_payment,
    create_misticpay_payment_from_settings,
    check_mp_payment_from_settings,
    check_efi_payment_from_settings,
    check_pagbank_payment_from_settings,
    check_picpay_payment_from_settings,
    check_pushinpay_payment_from_settings,
    check_stripe_payment_from_settings,
    check_paypal_payment_from_settings,
    check_asaas_payment_from_settings,
    check_coinbase_payment_from_settings,
    check_nowpayments_invoice_from_settings,
    check_manual_pix_payment,
    check_misticpay_payment_from_settings,
    approve_manual_pix_payment,
)
from functions.payments.create_payment import BASE_URL as PAY_API_BASE
from .stock_manager import StockManager
from .delivery import process_automatic_delivery, send_payment_approved_dm
from .purchase_manager import PurchaseManager
from .coupon_validator import CouponValidator
from modules.loja.logs.purchase_logs import PurchaseLogsSystem
from .buy_modal import ensure_emoji
from functions.plan import is_free, should_allow_payment_provider
from functions.promotions import get_effective_price
from modules.manager_integration.client import schedule_manager_notification

def _find_first(data: Any, keys: List[str]) -> Optional[Any]:
    """Busca recursiva por chaves em estrutura de dados"""
    if isinstance(data, dict):
        for k in keys:
            if k in data and data[k]:
                return data[k]
        for v in data.values():
            r = _find_first(v, keys)
            if r:
                return r
    elif isinstance(data, list):
        for it in data:
            r = _find_first(it, keys)
            if r:
                return r
    return None




def build_promisse_cart_action_rows(
    *,
    thread_id: int | str,
    item_options: list[disnake.SelectOption],
    available_payment_keys: list[str],
    final_price: float,
) -> list[disnake.ui.ActionRow]:
    """Monta as ações do carrinho no mesmo fluxo visual dos vídeos de referência.

    Um único item mostra a edição direta de quantidade. Com dois ou mais itens,
    a edição passa para o seletor ``Gerenciar produtos no carrinho``. A tela
    inicial não exibe ações redundantes de atualizar, adicionar ou cancelar.
    """
    continue_button = disnake.ui.Button(
        label="Ir para pagamento",
        emoji=ensure_emoji(emoji.pix),
        style=disnake.ButtonStyle.green,
        custom_id=f"cart_continue:{thread_id}",
        disabled=not bool(available_payment_keys) and final_price > 0,
    )
    coupon_button = disnake.ui.Button(
        label="Usar cupom de desconto",
        emoji=ensure_emoji(getattr(emoji, "coupon", emoji.coin)),
        style=disnake.ButtonStyle.grey,
        custom_id=f"cart_apply_coupon:{thread_id}",
    )
    terms_button = disnake.ui.Button(
        label="Ler Termos e Condições",
        emoji=ensure_emoji(getattr(emoji, "termos", getattr(emoji, "textc", emoji.shield))),
        style=disnake.ButtonStyle.primary,
        custom_id=f"cart_view_terms:{thread_id}",
    )

    if len(item_options) <= 1:
        edit_button = disnake.ui.Button(
            label="Editar quantidade",
            emoji=ensure_emoji(getattr(emoji, "edit", emoji.config)),
            style=disnake.ButtonStyle.primary,
            custom_id=f"cart_edit_items:{thread_id}",
        )
        return [
            disnake.ui.ActionRow(continue_button, edit_button),
            disnake.ui.ActionRow(coupon_button, terms_button),
        ]

    manager_select = disnake.ui.StringSelect(
        custom_id=f"cart_manage_item:{thread_id}",
        placeholder="Gerenciar produtos no carrinho",
        min_values=1,
        max_values=1,
        options=item_options[:25],
    )
    return [
        disnake.ui.ActionRow(continue_button),
        disnake.ui.ActionRow(manager_select),
        disnake.ui.ActionRow(coupon_button, terms_button),
    ]

def _extract_urls(data: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extrai URLs de checkout e código PIX"""
    checkout = _find_first(data, [
        "checkout_url", "url", "init_point", "init_url",
        "invoice_url", "payment_url", "hosted_url", "link",
        "paymentLinkUrl"  # Carteira Integrada
    ])
    copy_code = _find_first(data, [
        "copy_paste", "pix_copia_cola", "emv", "code",
        "qr_code_text", "qrcode_text",
        "pixCopyPaste", "qrCode"  # Carteira Integrada
    ])
    return str(checkout) if checkout else None, str(copy_code) if copy_code else None


def _extract_qr_image(data: Dict[str, Any]) -> tuple[Optional[bytes], Optional[str]]:
    """Extrai imagem QR Code"""
    # Primeiro tentar qr_code_bytes direto (PushinPay, PagBank, PIX Manual)
    qr_bytes = _find_first(data, ["qr_code_bytes"])
    if isinstance(qr_bytes, bytes):
        return qr_bytes, None
    
    # Tentar base64
    b64 = _find_first(data, ["qr_code_base64", "qrcode_base64", "qr_base64", "base64"])
    if isinstance(b64, str):
        try:
            if b64.startswith("data:") and "," in b64:
                b64 = b64.split(",", 1)[1]
            raw = base64.b64decode(b64)
            return raw, "qrcode.png"
        except Exception:
            pass
    
    # Tentar URL
    url = _find_first(data, ["qr_code_url", "qrcode_url", "qr_url", "image", "qr_code_image_url", "qrCodeImage"])  # Carteira Integrada
    return None, str(url) if url else None


def _api_base_root() -> str:
    """Retorna a URL base da API"""
    base = PAY_API_BASE.rstrip("/")
    if "/api/" in base:
        return base.split("/api/", 1)[0]
    return base


def _cart_url(thread: disnake.Thread) -> str:
    return f"https://discord.com/channels/{thread.guild.id}/{thread.id}"

def _resolve_cart_thread_host(inter: disnake.Interaction):
    """Retorna o canal de texto onde o tópico privado do carrinho será criado.

    Interações podem acontecer dentro de um tópico já existente. Objetos
    ``disnake.Thread`` não possuem ``create_thread``; nesse caso usamos o canal
    pai. Isso evita o erro ``'Thread' object has no attribute 'create_thread'``
    sem alterar o restante do fluxo do carrinho.
    """
    channel = getattr(inter, "channel", None)
    guild = getattr(inter, "guild", None)

    if isinstance(channel, disnake.Thread):
        parent = getattr(channel, "parent", None)
        if parent is None and guild is not None:
            parent_id = getattr(channel, "parent_id", None)
            if parent_id:
                parent = guild.get_channel(parent_id)
        channel = parent

    if isinstance(channel, disnake.TextChannel):
        return channel

    # Compatibilidade com mocks e subclasses que implementem create_thread,
    # mas nunca aceite outro Thread como host.
    if channel is not None and not isinstance(channel, disnake.Thread):
        creator = getattr(channel, "create_thread", None)
        if callable(creator):
            return channel

    return None



def _cart_link_components(thread: disnake.Thread) -> list[disnake.ui.ActionRow]:
    return [
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Ir para o carrinho",
                style=disnake.ButtonStyle.url,
                emoji=emoji.cart,
                url=_cart_url(thread),
            )
        )
    ]


def _money_br(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_cart_products(
    items: List[Dict[str, Any]],
    products: Dict[str, Any],
    *,
    limit: int = 10,
) -> tuple[str, int]:
    """Formata os produtos do carrinho em blocos curtos e legíveis.

    Retorna o texto pronto para embed/componentes e o total de unidades. O
    formato é compartilhado pelo carrinho, seleção do método e pagamento para
    evitar diferenças entre as telas.
    """
    blocks: list[str] = []
    total_units = 0

    for index, item in enumerate((items or [])[: max(1, int(limit or 10))], start=1):
        product = products.get(item.get("product_id"), {}) or {}
        product_name = str(product.get("name") or "Produto").strip() or "Produto"
        campo = (product.get("campos") or {}).get(item.get("campo_id"), {}) or {}
        option_name = str(campo.get("name") or "").strip()
        quantity = max(1, int(item.get("quantity", 1) or 1))
        item_total = float(item.get("item_total", 0) or 0)
        unit_price = float(item.get("price_per_unit", 0) or 0)
        if unit_price <= 0 and quantity > 0:
            unit_price = item_total / quantity

        total_units += quantity
        details = []
        if option_name and option_name.casefold() not in {"padrão", "padrao", "opção", "opcao"}:
            details.append(
                f"> {getattr(emoji, 'settings2', emoji.config)} **Opção selecionada:** `{option_name[:80]}`"
            )
        details.extend([
            f"> {emoji.cart} **Quantidade:** `{quantity}`",
            f"> {getattr(emoji, 'dollar', emoji.coin)} **Valor unitário:** `{_money_br(unit_price)}`",
            f"> {emoji.coin} **Subtotal do item:** `{_money_br(item_total)}`",
        ])
        blocks.append(
            f"{getattr(emoji, 'cardbox', emoji.cart)} **{index:02d} • {product_name[:76]}**\n"
            + "\n".join(details)
        )

    hidden = max(0, len(items or []) - max(1, int(limit or 10)))
    if hidden:
        blocks.append(f"-# E mais {hidden} produto(s) no carrinho.")

    return "\n\n".join(blocks) or "`Carrinho vazio`", total_units


def _chunk_buttons(buttons: list[disnake.ui.Button], size: int = 5) -> list[disnake.ui.ActionRow]:
    rows: list[disnake.ui.ActionRow] = []
    for index in range(0, len(buttons), size):
        chunk = buttons[index:index + size]
        if chunk:
            rows.append(disnake.ui.ActionRow(*chunk))
    return rows


def _integrated_wallet_preview(amount: float, payment_method: str) -> Optional[dict]:
    """Prévia das taxas da Carteira Integrada usada no checkout.

    A prévia só aparece quando a Carteira Integrada estiver ativada e com a
    chave PurinCash global configurada. O cálculo definitivo é repetido na
    criação da cobrança para impedir divergências.
    """
    if payment_method != "pix" or amount <= 0:
        return None
    try:
        from functions.payments.sync_wallet import calculate_store_fee, global_wallet_is_configured

        configs = db.get_document("payment_configs") or {}
        pagamentos = db.get_document("pagamentos") or {}
        entry = configs.get("sync_wallet") or {}
        if not isinstance(entry, dict):
            entry = {"enabled": bool(entry)}
        enabled = bool(entry.get("enabled", pagamentos.get("sync_wallet", False)))
        if not enabled or not global_wallet_is_configured() or not should_allow_payment_provider("sync_wallet"):
            return None
        return calculate_store_fee(amount, entry)
    except Exception:
        return None


async def _respond_cart_success(
    inter: disnake.Interaction,
    thread: disnake.Thread,
    loading_msg: Optional[disnake.Message] = None,
    *,
    created: bool = False,
) -> None:
    action = "Carrinho criado" if created else "Produto adicionado ao carrinho"
    content = (
        f"{emoji.correct} **{action} com sucesso!**\n"
        f"{emoji.cart} Continue a compra no carrinho privado ou adicione outros produtos."
    )
    components = _cart_link_components(thread)
    if loading_msg is not None:
        try:
            await loading_msg.edit(content=content, components=components)
            return
        except Exception:
            pass
    try:
        await inter.edit_original_message(content=content, embed=None, components=components)
        return
    except (disnake.NotFound, disnake.HTTPException, AttributeError):
        pass
    except Exception:
        pass
    try:
        await inter.followup.send(content=content, components=components, ephemeral=True)
    except Exception:
        pass


async def _send_whatsapp_notification(product_name: str, value: str, buyer_name: str):
    """Envia notificação de venda para a API do WhatsApp"""
    try:
        # Obter configuração de notificação
        notif_config = db.get_document("notifications_config") or {}
        
        if not notif_config.get("enabled"):
            return
            
        ddd = notif_config.get("ddd")
        number = notif_config.get("number")
        
        if not ddd or not number:
            return
            
        url = "https://notify.syncapplications.com.br/notify-sale"
        data = {
            "productName": product_name,
            "value": value,
            "buyerName": buyer_name,
            "ddd": ddd,
            "number": number
        }
        
        print(f"[WhatsApp] Tentando enviar notificação: {data}")
        # Timeout curto para não travar o bot
        t = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=t) as session:
            async with session.post(url, json=data) as resp:
                status = resp.status
                text = await resp.text()
                print(f"[WhatsApp] Status: {status} | Resposta: {text}")
                if status != 200:
                    print(f"[WhatsApp] ❌ Falha na API: {status} - {text}")
                else:
                    print(f"[WhatsApp] ✅ Notificação enviada com sucesso!")
    except Exception as e:
        print(f"[WhatsApp] Erro ao enviar notificação: {e}")


async def _http_get_bytes(url: str, timeout: int = 15) -> Optional[bytes]:
    """Baixa bytes de uma URL"""
    try:
        t = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=t) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception:
        return None
    return None


def _extract_payment_ids(data: Dict[str, Any]) -> Dict[str, str]:
    """Extrai IDs de pagamento"""
    out: Dict[str, str] = {}
    # Incluir txid para Efí, paymentId e correlationID para Carteira Integrada
    for k in ["payment_id", "paymentId", "id", "correlationID", "payment_intent", "charge", "preference_id", "invoice_id", "txid"]:
        v = _find_first(data, [k])
        if v:
            out[k] = str(v)
    return out


def _migrate_cart_to_items(cart: Dict[str, Any]) -> Dict[str, Any]:
    """Migra carrinho antigo (sem items) para nova estrutura com items"""
    if "items" in cart:
        # Verificar se items estão válidos
        items = cart.get("items", [])
        if items and all(item.get("product_id") and item.get("campo_id") for item in items):
            return cart  # Já está na nova estrutura e items são válidos
        elif items:
            # Items existem mas estão inválidos - tentar migrar do formato antigo se possível
            if cart.get("product_id") and cart.get("campo_id"):
                # Criar items válidos do formato antigo
                items = [{
                    "product_id": cart.get("product_id"),
                    "campo_id": cart.get("campo_id"),
                    "quantity": cart.get("quantity", 1),
                    "price_per_unit": cart.get("price_per_unit", 0),
                    "item_total": cart.get("price_per_unit", 0) * cart.get("quantity", 1)
                }]
                cart["items"] = items
                return cart
    
    # Criar estrutura nova com items
    items = [{
        "product_id": cart.get("product_id"),
        "campo_id": cart.get("campo_id"),
        "quantity": cart.get("quantity", 1),
        "price_per_unit": cart.get("price_per_unit", 0),
        "item_total": cart.get("price_per_unit", 0) * cart.get("quantity", 1)
    }]
    
    cart["items"] = items
    return cart


def _migrate_payment_data(cart: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migra payment_data antiga para nova estrutura organizada
    
    Nova estrutura separa:
    - local: Dados de interface do bot (copy_code, qr_url, etc.)
    - provider: Dados específicos do provedor (payment_id, correlation_id, etc.)
    - metadata: Informações contextuais (created_at, payment_method, amount)
    """
    payment_data = cart.get("payment_data", {})
    
    # Se já está na nova estrutura, retornar
    if "local" in payment_data and "provider" in payment_data:
        return cart
    
    # Se não tem payment_data, retornar
    if not payment_data:
        return cart
    
    # Migrar para nova estrutura
    new_payment_data = {
        "local": {
            "copy_code": payment_data.get("copy_code"),
            "qr_url": payment_data.get("qr_url"),
            "qr_bytes": payment_data.get("qr_bytes"),
            "requires_manual_approval": payment_data.get("requires_manual_approval", False)
        },
        "provider": {
            "name": payment_data.get("payment_provider"),
            "raw_response": payment_data.get("raw", {})
        },
        "metadata": {
            "created_at": cart.get("created_at"),
            "payment_method": cart.get("payment_method"),
            "amount": cart.get("total_price"),
            "currency": "BRL"
        }
    }
    
    # Extrair IDs do payment_ids (estrutura antiga)
    payment_ids = payment_data.get("payment_ids", {})
    if payment_ids:
        for key, value in payment_ids.items():
            # Normalizar nomes de chaves
            if key in ["payment_id", "paymentId"]:
                new_payment_data["provider"]["payment_id"] = value
            elif key in ["correlationID", "correlation_id"]:
                new_payment_data["provider"]["correlation_id"] = value
            elif key in ["charge_id", "chargeId"]:
                new_payment_data["provider"]["charge_id"] = value
            elif key == "txid":
                new_payment_data["provider"]["txid"] = value
            else:
                new_payment_data["provider"][key] = value
    
    # Fallback: tentar extrair IDs diretamente do raw
    raw_data = payment_data.get("raw", {})
    if raw_data and not payment_ids:
        if "paymentId" in raw_data:
            new_payment_data["provider"]["payment_id"] = raw_data["paymentId"]
        if "correlationID" in raw_data:
            new_payment_data["provider"]["correlation_id"] = raw_data["correlationID"]
        if "id" in raw_data:
            new_payment_data["provider"]["charge_id"] = raw_data["id"]
        if "txid" in raw_data:
            new_payment_data["provider"]["txid"] = raw_data["txid"]
    
    cart["payment_data"] = new_payment_data
    return cart


async def _find_user_open_cart(user_id: int, guild_id: int, delivery_type: str, bot=None, guild=None, loja_data_cache: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """Encontra carrinho aberto do usuário no servidor (permite tipos de entrega mistos quando em status 'cart')"""
    # Usar cache se fornecido, senão carregar do banco
    if loja_data_cache is None:
        loja_data = db.get_document("loja_data")
    else:
        loja_data = loja_data_cache
    
    carts = loja_data.get("carts", {})
    
    orphaned_carts = []  # Lista de carrinhos órfãos para limpeza
    current_time = int(datetime.utcnow().timestamp())
    
    for cart_id, cart in carts.items():
        cart_user_id = cart.get("user_id")
        cart_guild_id = cart.get("guild_id")
        cart_status = cart.get("status", "pending")
        
        # Comparar user_id e guild_id (garantir tipos compatíveis)
        if (cart_user_id == user_id or str(cart_user_id) == str(user_id)) and \
           (cart_guild_id == guild_id or str(cart_guild_id) == str(guild_id)):
            
            # Aceitar carrinhos em status "cart" (antes do pagamento) - permite tipos de entrega mistos
            # Para status "pending" (em pagamento), não permitir adicionar mais itens
            if cart_status == "cart":
                
                # VERIFICAÇÃO CRÍTICA: Verificar se a thread ainda existe
                thread_id = cart.get("thread_id")
                thread_exists = False
                
                if thread_id:
                    # Verificar se o carrinho foi criado recentemente (últimos 30 segundos)
                    # Se sim, assumir que a thread existe (pode estar sendo criada ainda)
                    created_at = cart.get("created_at", 0)
                    is_recent = (current_time - created_at) < 30  # 30 segundos (aumentado para evitar verificações desnecessárias)
                    
                    if is_recent:
                        thread_exists = True
                    else:
                        # Tentar obter guild se não foi passado
                        check_guild = guild
                        if not check_guild and bot:
                            try:
                                check_guild = bot.get_guild(int(guild_id))
                            except:
                                pass
                        
                        if check_guild:
                            try:
                                # Tentar get_thread primeiro (mais rápido, usa cache)
                                thread = check_guild.get_thread(int(thread_id))
                                if thread:
                                    thread_exists = True
                                # Só fazer fetch_channel se get_thread falhar (mais lento)
                                # Removido para melhorar performance - assumir que thread existe se não está no cache
                                # pois fetch_channel é muito lento
                            except Exception:
                                thread_exists = False
                        else:
                            # Se não temos guild para verificar, assumir que thread existe (evitar falsos positivos)
                            thread_exists = True
                
                if not thread_exists:
                    orphaned_carts.append(cart_id)
                    continue  # Pular este carrinho
                
                # Migrar se necessário
                cart = _migrate_cart_to_items(cart)
                
                # Verificar se tem items válidos
                items = cart.get("items", [])
                
                # Aceitar carrinho mesmo se não tiver items ainda (pode estar sendo criado)
                if not items:
                    return cart_id, cart
                
                if items and all(item.get("product_id") and item.get("campo_id") for item in items):
                    # Retornar o carrinho - permite adicionar produtos com tipos de entrega diferentes
                    return cart_id, cart
                elif items:
                    # Retornar mesmo assim para tentar adicionar
                    return cart_id, cart
    
    # Limpar carrinhos órfãos encontrados (só se não estivermos usando cache)
    if orphaned_carts and loja_data_cache is None:
        loja_data = db.get_document("loja_data")
        for orphan_id in orphaned_carts:
            if orphan_id in loja_data.get("carts", {}):
                del loja_data["carts"][orphan_id]
        db.save_document("loja_data", loja_data)
    
    return None, None


async def _close_approved_cart_later(
    thread: disnake.Thread,
    cart_id: str,
    delay_seconds: int = 180,
) -> None:
    """Fecha e bloqueia o carrinho três minutos após a aprovação."""
    try:
        await asyncio.sleep(max(0, int(delay_seconds)))
        await thread.edit(locked=True, archived=True)

        loja_data = db.get_document("loja_data") or {}
        cart = (loja_data.get("carts") or {}).get(cart_id)
        if cart:
            cart["cart_closed_at"] = int(time.time())
            cart["cart_auto_closed"] = True
            loja_data["carts"][cart_id] = cart
            db.save_document("loja_data", loja_data)
    except (disnake.NotFound, disnake.Forbidden):
        return
    except Exception as exc:
        print(f"[CHECKOUT] Não foi possível fechar o carrinho {getattr(thread, 'id', '?')}: {exc}")


def _build_approved_checkout_message(
    cart: Dict[str, Any],
    items: List[Dict[str, Any]],
    products: Dict[str, Any],
    delivered_automatically: bool,
    manual_items_count: int,
    dm_channel_id: Optional[int] = None,
    mode: str = "embed"
) -> tuple[Optional[disnake.Embed], Optional[List], Optional[str]]:
    """Constrói a confirmação de pagamento no estilo profissional da referência."""
    total_price = float(cart.get("total_price", 0) or 0)
    discount_amount = float(cart.get("discount_amount", 0) or 0)
    balance_applied = float(cart.get("balance_applied", 0) or 0)
    final_price = max(0.0, total_price - discount_amount - balance_applied)
    close_at = int(cart.get("auto_close_at") or (time.time() + 180))

    product_lines = []
    total_quantity = 0
    for item in items:
        product_id = item.get("product_id")
        campo_id = item.get("campo_id")
        quantity = max(1, int(item.get("quantity", 1) or 1))
        item_total = float(item.get("item_total", 0) or 0)
        product = products.get(product_id, {}) or {}
        product_name = str(product.get("name") or "Produto")
        campo = (product.get("campos") or {}).get(campo_id, {}) or {}
        campo_name = str(campo.get("name") or "Padrão")
        total_quantity += quantity
        option_text = f" • `{campo_name}`" if campo_name.lower() not in {"padrão", "padrao", "opção", "opcao"} else ""
        product_lines.append(
            f"• `{quantity}x` **{product_name}**{option_text} — `{_money_br(item_total)}`"
        )

    if not product_lines:
        product_lines.append("• Produto processado com sucesso")

    # Produto entregue na sua DM: frase mantida para compatibilidade e clareza do fluxo.
    if delivered_automatically and manual_items_count == 0:
        status = "Entregue"
        delivery_title = "📦 Entrega realizada!"
        delivery_text = (
            "Seu produto foi entregue com sucesso. Verifique suas mensagens diretas (DM) "
            "para acessar o produto."
        )
    elif manual_items_count > 0:
        status = "Aguardando entrega"
        delivery_title = "📦 Entrega em andamento"
        delivery_text = (
            f"O pagamento foi confirmado. `{manual_items_count}` produto(s) serão entregues "
            "pela equipe diretamente na sua DM."
        )
    else:
        status = "Requer suporte"
        delivery_title = "⚠️ Entrega não concluída"
        delivery_text = (
            "O pagamento foi aprovado, mas não foi possível concluir a entrega na DM. "
            "Ative suas mensagens privadas e procure o suporte."
        )

    information_text = (
        "\n".join(product_lines)
        + f"\n\n**Quantidade:** `{total_quantity or 1}`"
        + f"\n**Valor:** `{_money_br(final_price)}`"
        + f"\n**Status:** `{status}`"
    )

    action_buttons = []
    if dm_channel_id:
        action_buttons.append(
            disnake.ui.Button(
                label="Ir para DM",
                style=disnake.ButtonStyle.url,
                emoji="💬",
                url=f"https://discord.com/channels/@me/{int(dm_channel_id)}",
            )
        )
    if manual_items_count > 0:
        cart_id = cart.get("cart_id") or cart.get("thread_id")
        action_buttons.append(
            disnake.ui.Button(
                label="Encerrar Atendimento",
                style=disnake.ButtonStyle.red,
                custom_id=f"close_cart:{cart_id}",
                emoji=getattr(emoji, "delete", "🗑️"),
            )
        )
    button_rows = [disnake.ui.ActionRow(*action_buttons[:5])] if action_buttons else []

    if mode == "embed":
        embed = disnake.Embed(
            title="✅ Pagamento Aprovado!",
            description="Seu pagamento foi processado com sucesso!",
            color=disnake.Color.green(),
            timestamp=disnake.utils.utcnow(),
        )
        embed.add_field(name="📋 Informações da Compra", value=information_text[:1024], inline=False)
        embed.add_field(name=delivery_title, value=delivery_text, inline=False)
        embed.add_field(
            name="🔒 Compra segura",
            value=(
                "Não compartilhe os dados recebidos na DM. Caso precise de ajuda, entre em contato com o suporte.\n"
                f"Este carrinho será fechado em <t:{close_at}:R>."
            ),
            inline=False,
        )
        embed.set_footer(text="ZYNEX Systems • Pagamento confirmado")
        return embed, button_rows, None

    colors = db.get_document("custom_colors") or {}
    raw_color = str(colors.get("primary") or "").replace("#", "")
    try:
        accent = disnake.Colour(int(raw_color, 16)) if raw_color else disnake.Color.green()
    except Exception:
        accent = disnake.Color.green()

    container = disnake.ui.Container(
        disnake.ui.TextDisplay("# ✅ Pagamento Aprovado!"),
        disnake.ui.TextDisplay("Seu pagamento foi processado com sucesso!"),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay(f"## 📋 Informações da Compra\n{information_text}"),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay(f"## {delivery_title}\n{delivery_text}"),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay(
            "## 🔒 Compra segura\n"
            "Não compartilhe os dados recebidos na DM. Caso precise de ajuda, entre em contato com o suporte.\n"
            f"-# Este carrinho será fechado em <t:{close_at}:R>."
        ),
        accent_colour=accent,
    )
    return None, [container] + button_rows, None


async def _build_cart_message(cart: Dict[str, Any], thread: disnake.Thread, mode: str) -> disnake.Message:
    """Constrói um carrinho premium, organizado e totalmente interativo.

    A interface mantém as ações principais visíveis e move a edição detalhada
    para menus privados, evitando poluição visual e limites de componentes.
    """
    products = db.get_document("loja_products") or {}
    items = cart.get("items", []) or []
    if not items:
        return None

    total_price = sum(float(item.get("item_total", 0) or 0) for item in items)
    discount_amount = float(cart.get("discount_amount", 0) or 0)
    coupon_code = cart.get("coupon_code")
    balance_applied = float(cart.get("balance_applied", 0) or 0)
    final_price = max(0.0, total_price - discount_amount - balance_applied)
    payment_method = str(cart.get("payment_method", "pix") or "pix")
    updated_ts = int(datetime.utcnow().timestamp())
    user_id = int(cart.get("user_id", 0) or 0)
    user_mention = f"<@{user_id}>" if user_id else "Cliente"
    total_units = sum(max(1, int(item.get("quantity", 1) or 1)) for item in items)
    order_reference = str(cart.get("order_id") or thread.id)[-10:]
    created_ts = int(cart.get("created_at") or cart.get("created_timestamp") or updated_ts)

    # Saldo disponível.
    balance_info = {"enabled": False, "can_apply": False, "user_balance": 0, "usable_amount": 0}
    try:
        from modules.loja.saldo.checkout_integration import SaldoCheckoutIntegration
        if user_id:
            balance_info = SaldoCheckoutIntegration.get_cart_balance_info(cart, user_id)
    except Exception:
        pass

    # Cashback estimado.
    cashback_amount = 0.0
    try:
        from modules.loja.cashback.manager import CashbackManager
        if user_id and CashbackManager.is_enabled():
            user_roles = []
            member = thread.guild.get_member(user_id) if thread and thread.guild else None
            if member:
                user_roles = [role.id for role in member.roles]
            cashback_amount = float(CashbackManager.calculate_cashback(final_price, user_roles) or 0)
    except Exception:
        pass

    # Métodos de pagamento realmente disponíveis.
    def _get_available_payment_method_keys() -> list[str]:
        global _payment_methods_cache
        current_time = time.time()
        if (
            _payment_methods_cache["data"] is not None
            and (current_time - _payment_methods_cache["timestamp"]) < _payment_methods_cache["ttl"]
        ):
            return list(_payment_methods_cache["data"])

        pagamentos_doc = db.get_document("pagamentos") or {}
        payment_configs = db.get_document("payment_configs") or {}
        functional_pix_providers = (
            "sync_wallet", "mercado_pago", "efibank", "pushinpay", "misticpay", "pix_manual"
        )

        def _entry(provider: str) -> dict:
            value = payment_configs.get(provider, {})
            return value if isinstance(value, dict) else {"enabled": bool(value)}

        def _enabled(provider: str, entry: dict) -> bool:
            return bool(entry.get("enabled", pagamentos_doc.get(provider, False)))

        def _configured(provider: str, entry: dict) -> bool:
            if provider == "sync_wallet":
                from functions.payments.sync_wallet import global_wallet_is_configured
                return global_wallet_is_configured()
            if provider == "mercado_pago":
                return bool(entry.get("access_token"))
            if provider == "efibank":
                return bool(
                    (entry.get("client_id") or entry.get("client"))
                    and (entry.get("client_secret") or entry.get("token"))
                    and entry.get("pix_key") and entry.get("cert_file")
                )
            if provider == "pushinpay":
                return bool(entry.get("token_pushinpay") or entry.get("access_token") or entry.get("token"))
            if provider == "misticpay":
                return bool(entry.get("client_id") and entry.get("client_secret"))
            if provider == "pix_manual":
                return bool(entry.get("pix_key") and entry.get("pix_key_type"))
            return False

        pix_available = any(
            should_allow_payment_provider(provider)
            and _enabled(provider, _entry(provider))
            and _configured(provider, _entry(provider))
            for provider in functional_pix_providers
        )
        available = ["pix"] if pix_available else []
        _payment_methods_cache["data"] = available
        _payment_methods_cache["timestamp"] = current_time
        return available

    # Usa a mesma fonte de disponibilidade do modal e da seleção de pagamento.
    try:
        from .buy_modal import get_available_payment_methods
        available_payment_keys = list((get_available_payment_methods() or {}).keys())
    except Exception:
        available_payment_keys = _get_available_payment_method_keys()
    wallet_preview = _integrated_wallet_preview(final_price, payment_method)

    color_data = db.get_document("custom_colors") or {}
    primary_color = color_data.get("primary")
    product_color = None
    if primary_color:
        try:
            product_color = disnake.Colour(int(str(primary_color).replace("#", ""), 16))
        except Exception:
            product_color = None

    method_names = {"pix": "PIX", "card": "Cartão de Crédito", "crypto": "Criptomoeda", "balance": "Saldo"}
    payment_display = method_names.get(payment_method, payment_method.upper())

    # Informações dos produtos e opções do seletor de gerenciamento.
    item_blocks: list[str] = []
    compact_item_lines: list[str] = []
    item_options: list[disnake.SelectOption] = []
    automatic_count = 0
    manual_count = 0
    for idx, item in enumerate(items[:25]):
        product = products.get(item.get("product_id"), {}) or {}
        product_name = str(product.get("name") or "Produto")
        campo = (product.get("campos") or {}).get(item.get("campo_id"), {}) or {}
        option_name = str(campo.get("name") or "Opção")
        quantity = max(1, int(item.get("quantity", 1) or 1))
        unit_price = float(item.get("price_per_unit", 0) or 0)
        item_total = float(item.get("item_total", unit_price * quantity) or 0)
        delivery_type = str((product.get("info") or {}).get("delivery_type", "automatic") or "automatic")

        infinite_data = campo.get("infinite_stock") or {}
        is_infinite = bool(infinite_data.get("enabled", False))
        if delivery_type == "manual":
            delivery_label = "Manual, entregue após confirmação"
            stock_label = "Sob atendimento"
            manual_count += 1
        else:
            delivery_label = "Automática na DM após aprovação"
            automatic_count += 1
            if is_infinite:
                stock_label = "Disponível"
            else:
                try:
                    stock_count = int(StockManager.get_available_stock(item.get("product_id"), item.get("campo_id")) or 0)
                    stock_label = f"{stock_count} unidade(s) disponível(is)"
                except Exception:
                    stock_label = "Verificado no pagamento"

        item_blocks.append(
            f"### `{idx + 1:02d}` {getattr(emoji, 'cardbox', emoji.cart)} {product_name}\n"
            f"> {getattr(emoji, 'settings2', emoji.config)} **Opção escolhida:** `{option_name}`\n"
            f"> {emoji.cart} **Quantidade:** `{quantity}`  •  **Valor unitário:** `{_money_br(unit_price)}`\n"
            f"> {emoji.coin} **Total deste produto:** `{_money_br(item_total)}`\n"
            f"> {getattr(emoji, 'truck', emoji.cart)} **Entrega:** `{delivery_label}`\n"
            f"> {getattr(emoji, 'verified', emoji.correct)} **Disponibilidade:** `{stock_label}`"
        )
        compact_item_lines.append(
            f"`{quantity}x {product_name[:28]}` • `{_money_br(item_total)}`"
            + (f" • `{option_name[:24]}`" if option_name else "")
        )
        item_options.append(
            disnake.SelectOption(
                label=product_name[:100],
                value=str(idx),
                description=f"{option_name} • {quantity}x • {_money_br(item_total)}"[:100],
                emoji=ensure_emoji(getattr(emoji, "cardbox", emoji.cart)),
            )
        )

    summary_lines = [
        f"{emoji.coin} **Subtotal:** `{_money_br(total_price)}`",
    ]
    if discount_amount > 0:
        summary_lines.append(f"{getattr(emoji, 'receipt', emoji.coin)} **Desconto:** `-{_money_br(discount_amount)}`")
    if coupon_code:
        summary_lines.append(f"{getattr(emoji, 'receipt', emoji.coin)} **Cupom aplicado:** `{coupon_code}`")
    if balance_applied > 0:
        summary_lines.append(f"{emoji.wallet} **Saldo utilizado:** `-{_money_br(balance_applied)}`")

    charged_amount = final_price
    if wallet_preview:
        store_fee = float(wallet_preview.get("store_fee_amount", 0) or 0)
        provider_fee = float(wallet_preview.get("provider_fee_amount", 0) or 0)
        responsibility = str(wallet_preview.get("responsibility") or "client")
        charged_amount = float(wallet_preview.get("charged_amount", final_price) or final_price)
        if store_fee > 0:
            summary_lines.append(f"{emoji.wallet} **Taxa da Loja:** `+{_money_br(store_fee)}`")
        if provider_fee > 0 and responsibility == "client":
            summary_lines.append(f"{emoji.pix} **Taxa de operação:** `+{_money_br(provider_fee)}`")

    summary_lines.extend([
        f"{getattr(emoji, 'verified', emoji.correct)} **Total no PIX:** `{_money_br(charged_amount)}`",
        f"{emoji.pix} **Forma de pagamento:** `{payment_display}`",
    ])
    if cashback_amount > 0:
        summary_lines.append(f"{getattr(emoji, 'gift', emoji.coin)} **Cashback estimado:** `+{_money_br(cashback_amount)}`")

    delivery_summary = []
    if automatic_count:
        delivery_summary.append(f"{automatic_count} automática(s)")
    if manual_count:
        delivery_summary.append(f"{manual_count} manual(is)")
    if delivery_summary:
        summary_lines.append(f"{getattr(emoji, 'truck', emoji.cart)} **Entrega:** `{', '.join(delivery_summary)}`")

    try:
        from modules.loja.preferences.utils import get_terms
        terms_enabled, _terms_text = get_terms()
    except Exception:
        terms_enabled = False

    # Ações no mesmo fluxo do vídeo: edição direta para um item e seletor para vários.
    action_rows = build_promisse_cart_action_rows(
        thread_id=thread.id,
        item_options=item_options,
        available_payment_keys=available_payment_keys,
        final_price=final_price,
    )

    # Produtos e valores usam o mesmo formato em todas as etapas do checkout.
    product_preview, formatted_total_units = _format_cart_products(items, products, limit=10)
    total_units = formatted_total_units or total_units

    cart_summary = [f"{emoji.coin} **Subtotal:** `{_money_br(total_price)}`"]
    if discount_amount > 0:
        cart_summary.append(
            f"{getattr(emoji, 'coupon', emoji.coin)} **Desconto:** `-{_money_br(discount_amount)}`"
        )
    if balance_applied > 0:
        cart_summary.append(f"{emoji.wallet} **Saldo utilizado:** `-{_money_br(balance_applied)}`")
    cart_summary.append(
        f"{getattr(emoji, 'correct', emoji.pix)} **Total do pedido:** `{_money_br(charged_amount)}`"
    )

    member = thread.guild.get_member(user_id) if thread.guild and user_id else None
    author_name = getattr(member, "display_name", None) or getattr(member, "name", None) or "Cliente"
    author_icon = None
    if member is not None:
        avatar = getattr(member, "display_avatar", None)
        author_icon = getattr(avatar, "url", None)

    embed = disnake.Embed(
        title=f"{getattr(emoji, 'cart', '🛒')} Seu carrinho",
        description=(
            "Confira os itens selecionados, ajuste as quantidades e prossiga quando estiver tudo certo."
        ),
        color=product_color or disnake.Color.blurple(),
    )
    if author_icon:
        embed.set_author(name=author_name, icon_url=author_icon)
    else:
        embed.set_author(name=author_name)
    embed.add_field(
        name=f"Produtos no carrinho • {len(items)} item(ns) • {total_units} unidade(s)",
        value=product_preview[:1024],
        inline=False,
    )
    embed.add_field(
        name="Resumo do pedido",
        value="\n".join(cart_summary)[:1024],
        inline=False,
    )

    guild_icon = getattr(getattr(thread.guild, "icon", None), "url", None) if thread.guild else None
    footer_name = getattr(thread.guild, "name", "Loja") if thread.guild else "Loja"
    if guild_icon:
        embed.set_footer(text=footer_name, icon_url=guild_icon)
    else:
        embed.set_footer(text=footer_name)
    embed.timestamp = datetime.utcnow()

    return await thread.send(content=user_mention, embed=embed, components=action_rows)

async def _add_item_to_cart(cart_id: str, product_id: str, campo_id: str, quantity: int, price: float, loja_data_cache: Optional[Dict] = None) -> Dict[str, Any]:
    """Adiciona item a carrinho existente"""
    # Usar cache se fornecido, senão carregar do banco
    if loja_data_cache is None:
        loja_data = db.get_document("loja_data")
    else:
        loja_data = loja_data_cache
    cart = loja_data.get("carts", {}).get(cart_id)
    
    if not cart:
        return None
    
    # Migrar se necessário
    cart = _migrate_cart_to_items(cart)
    
    # Verificar estoque ANTES de adicionar ao carrinho
    products = db.get_document("loja_products")
    product = products.get(product_id, {})
    if not product:
        return None
    
    campos = product.get("campos", {})
    campo = campos.get(campo_id, {})
    if not campo:
        return None
    
    info = product.get("info", {})
    delivery_type = info.get("delivery_type", "automatic")
    
    # Verificar se é estoque infinito
    infinite_stock = campo.get("infinite_stock", {})
    is_infinite = infinite_stock.get("enabled", False)
    
    if not is_infinite:
        # Verificar estoque disponível
        stock_count = StockManager.get_available_stock(product_id, campo_id)
        
        # Calcular quantidade total já no carrinho (excluindo o item que será adicionado/modificado)
        items = cart.get("items", [])
        total_quantity_in_cart = sum(
            it.get("quantity", 0) for it in items
            if it.get("product_id") == product_id and it.get("campo_id") == campo_id
        )
        
        # Estoque disponível considerando itens já no carrinho
        available_stock = stock_count - total_quantity_in_cart
        
        # Se for entrega automática e não houver estoque suficiente, não adicionar
        if delivery_type == "automatic" and available_stock < quantity:
            return None
        
        # Se for aumentar quantidade de item existente, verificar se a nova quantidade total não excede estoque
        if total_quantity_in_cart > 0:
            new_total_quantity = total_quantity_in_cart + quantity
            if delivery_type == "automatic" and new_total_quantity > stock_count:
                return None
    
    # Verificar se item já existe (mesmo produto e campo)
    items = cart.get("items", [])
    item_found = False
    for item in items:
        if item.get("product_id") == product_id and item.get("campo_id") == campo_id:
            # Aumentar quantidade
            item["quantity"] = item.get("quantity", 1) + quantity
            item["item_total"] = item["quantity"] * item.get("price_per_unit", price)
            item_found = True
            break
    
    if not item_found:
        # Adicionar novo item
        new_item = {
            "product_id": product_id,
            "campo_id": campo_id,
            "quantity": quantity,
            "price_per_unit": price,
            "item_total": price * quantity
        }
        items.append(new_item)
    
    cart["items"] = items
    cart["updated_at"] = int(datetime.utcnow().timestamp())
    
    # Recalcular total
    cart["total_price"] = sum(item.get("item_total", 0) for item in items)
    
    loja_data["carts"][cart_id] = cart
    db.save_document("loja_data", loja_data)
    
    return cart


async def create_checkout(
    inter: disnake.ModalInteraction,
    product_id: str,
    campo_id: Optional[str],
    quantity: int,
    payment_method: str,
    coupon_code: Optional[str] = None,
    loading_msg: Optional[disnake.Message] = None
):
    """
    Cria um checkout completo com tópico privado e pagamento.
    IMPORTANTE: Todas as validações pesadas (manutenção, horário, OAuth2, estoque) 
    devem ser feitas ANTES de chamar esta função.
    
    Args:
        loading_msg: Mensagem de loading opcional para editar ao invés de criar nova mensagem
    """
    
    # Carregar dados do produto (validação básica apenas)
    products = db.get_document("loja_products")
    product = products.get(product_id)
    
    if not product:
        if inter.response.is_done():
            await inter.followup.send(
                f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Produto não encontrado!",
                ephemeral=True
            )
        else:
            await inter.response.send_message(
                f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Produto não encontrado!",
                ephemeral=True
            )
        return

    if not product.get("active", True):
        sender = inter.followup.send if inter.response.is_done() else inter.response.send_message
        await sender(f"{emoji.wrong if hasattr(emoji, 'wrong') else '❌'} Produto indisponível.", ephemeral=True)
        return
    
    product_name = product.get("name", "Produto")
    campos = product.get("campos", {})
    
    # Se tem campo específico, validar
    if campo_id and campo_id != "none":
        campo = campos.get(campo_id)
        if not campo:
            if inter.response.is_done():
                await inter.followup.send(
                    f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Opção do produto não encontrada!",
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Opção do produto não encontrada!",
                    ephemeral=True
                )
            return
        campo_name = campo.get("name", "")
        price = get_effective_price(product, campo)
    else:
        # Se não tem campo específico, pegar o primeiro disponível
        if not campos:
            if inter.response.is_done():
                await inter.followup.send(
                    f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Produto sem opções disponíveis!",
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Produto sem opções disponíveis!",
                    ephemeral=True
                )
            return
        campo_id = list(campos.keys())[0]
        campo = campos[campo_id]
        campo_name = campo.get("name", "")
        price = get_effective_price(product, campo)
    
    # Calcular valor total
    total_price = price * quantity
    
    # Verificar modo de exibição
    mode = db.get_document("custom_mode").get("mode", "embed")
    
    # Obter tipo de entrega do produto
    info = product.get("info") or {}
    delivery_type = info.get("delivery_type", "automatic")
    
    # CRIAR E SALVAR CARRINHO ANTES DE MOSTRAR QUALQUER MENSAGEM
    # Carregar loja_data uma vez e reutilizar
    loja_data = db.get_document("loja_data")
    
    # VERIFICAÇÃO CRÍTICA: Buscar carrinho existente usando cache do banco
    bot_ref = inter.bot if hasattr(inter, 'bot') else None
    existing_cart_id, existing_cart = await _find_user_open_cart(
        inter.author.id, 
        inter.guild.id, 
        delivery_type, 
        bot=bot_ref, 
        guild=inter.guild,
        loja_data_cache=loja_data  # Passar cache para evitar múltiplas leituras
    )
    
    if existing_cart_id and existing_cart:
        
        # Verificar se a thread ainda existe antes de adicionar ao carrinho
        thread_id = existing_cart.get("thread_id")
        thread = None
        if thread_id:
            try:
                thread = inter.guild.get_thread(thread_id)
                if not thread:
                    # Tentar buscar a thread (pode estar em cache)
                    try:
                        thread = await inter.guild.fetch_channel(thread_id)
                        if not isinstance(thread, disnake.Thread):
                            thread = None
                    except:
                        thread = None
            except:
                thread = None
        
        if not thread:
            # Thread não existe mais - deletar carrinho antigo e criar novo
            if existing_cart_id in loja_data.get("carts", {}):
                del loja_data["carts"][existing_cart_id]
                db.save_document("loja_data", loja_data)
            # Continuar para criar novo carrinho
        else:
            # Thread existe - adicionar produto ao carrinho existente
            updated_cart = await _add_item_to_cart(existing_cart_id, product_id, campo_id, quantity, price, loja_data_cache=loja_data)
            
            if not updated_cart:
                # Não conseguiu adicionar (provavelmente falta de estoque)
                # Verificar estoque para dar mensagem apropriada
                stock_count = StockManager.get_available_stock(product_id, campo_id)
                is_infinite = stock_count == 999999
                
                if delivery_type == "automatic" and not is_infinite and stock_count <= 0:
                    # Sem estoque disponível - mostrar botão de notificação
                    notify_emoji = ensure_emoji(emoji.warn)
                    notify_button = disnake.ui.Button(
                        emoji=notify_emoji,
                        label="Receber notificação ao repor estoque",
                        style=disnake.ButtonStyle.grey,
                        custom_id=f"notify_stock:{product_id}:{campo_id}"
                    )
                    
                    if loading_msg:
                        try:
                            await loading_msg.edit(
                                content=f"{emoji.wrong} Sem estoque disponível para este item.",
                                components=[disnake.ui.ActionRow(notify_button)]
                            )
                        except:
                            try:
                                await inter.followup.send(
                                    content=f"{emoji.wrong} Sem estoque disponível para este item.",
                                    components=[disnake.ui.ActionRow(notify_button)],
                                    ephemeral=True
                                )
                            except:
                                pass
                    else:
                        try:
                            await inter.edit_original_message(
                                content=f"{emoji.wrong} Sem estoque disponível para este item.",
                                embed=None,
                                components=[disnake.ui.ActionRow(notify_button)]
                            )
                        except (disnake.NotFound, disnake.HTTPException):
                            try:
                                await inter.followup.send(
                                    content=f"{emoji.wrong} Sem estoque disponível para este item.",
                                    components=[disnake.ui.ActionRow(notify_button)],
                                    ephemeral=True
                                )
                            except:
                                pass
                    return
                else:
                    # Estoque insuficiente para a quantidade solicitada
                    items = existing_cart.get("items", [])
                    total_quantity_in_cart = sum(
                        it.get("quantity", 0) for it in items
                        if it.get("product_id") == product_id and it.get("campo_id") == campo_id
                    )
                    available_stock = stock_count - total_quantity_in_cart
                    
                    if loading_msg:
                        try:
                            await loading_msg.edit(
                                content=f"{emoji.wrong} Estoque insuficiente. Disponível: `{available_stock}`, solicitado: `{quantity}`.",
                                components=[]
                            )
                        except:
                            pass
                    else:
                        try:
                            await inter.edit_original_message(
                                content=f"{emoji.wrong} Estoque insuficiente. Disponível: `{available_stock}`, solicitado: `{quantity}`.",
                                embed=None,
                                components=[]
                            )
                        except (disnake.NotFound, disnake.HTTPException):
                            try:
                                await inter.followup.send(
                                    content=f"{emoji.wrong} Estoque insuficiente. Disponível: `{available_stock}`, solicitado: `{quantity}`.",
                                    ephemeral=True
                                )
                            except:
                                pass
                    return
            
            if updated_cart:
                # Atualizar delivery_type do carrinho baseado nos produtos
                # Reutilizar products já carregado anteriormente se disponível
                products = db.get_document("loja_products")
                items = updated_cart.get("items", [])
                delivery_types = set()
                for item in items:
                    prod = products.get(item.get("product_id"), {})
                    info = prod.get("info") or {}
                    item_delivery = info.get("delivery_type", "automatic")
                    delivery_types.add(item_delivery)
                
                # Se tem tipos mistos, marcar como "mixed", senão usar o tipo único
                if len(delivery_types) > 1:
                    updated_cart["delivery_type"] = "mixed"
                else:
                    updated_cart["delivery_type"] = list(delivery_types)[0] if delivery_types else "automatic"
                
                # Salvar carrinho atualizado (reutilizar loja_data)
                loja_data["carts"][existing_cart_id] = updated_cart
                db.save_document("loja_data", loja_data)
                
                # Atualizar mensagem do carrinho
                try:
                    cart_message_id = existing_cart.get("cart_message_id")
                    if cart_message_id:
                        try:
                            cart_msg = await thread.fetch_message(cart_message_id)
                            # Reconstruir mensagem do carrinho
                            new_cart_msg = await _build_cart_message(updated_cart, thread, mode)
                            # Deletar mensagem antiga
                            await cart_msg.delete()
                            # Atualizar ID da mensagem (reutilizar loja_data)
                            loja_data["carts"][existing_cart_id]["cart_message_id"] = new_cart_msg.id
                            db.save_document("loja_data", loja_data)
                        except Exception as e:
                            # Se não conseguir atualizar, criar nova mensagem
                            try:
                                new_cart_msg = await _build_cart_message(updated_cart, thread, mode)
                                loja_data["carts"][existing_cart_id]["cart_message_id"] = new_cart_msg.id
                                db.save_document("loja_data", loja_data)
                            except Exception as e2:
                                pass
                    else:
                        # Criar mensagem do carrinho
                        try:
                            new_cart_msg = await _build_cart_message(updated_cart, thread, mode)
                            loja_data["carts"][existing_cart_id]["cart_message_id"] = new_cart_msg.id
                            db.save_document("loja_data", loja_data)
                        except Exception as e:
                            pass
                    
                    # Enviar mensagem marcando o usuário e depois apagar
                    try:
                        mention_msg = await thread.send(f"{inter.author.mention} Produto adicionado ao carrinho!")
                        await asyncio.sleep(3)
                        try:
                            await mention_msg.delete()
                        except:
                            pass
                    except Exception as e:
                        pass
                    
                    await _respond_cart_success(inter, thread, loading_msg, created=False)
                    return
                except Exception:
                    await _respond_cart_success(inter, thread, loading_msg, created=False)
                    return
            else:
                # Se não conseguiu adicionar, continuar para criar novo carrinho
                pass
    else:
        pass
    
    # SEGUNDA VERIFICAÇÃO CRÍTICA: Verificar novamente se não foi criado um carrinho entre a primeira verificação e agora
    # (evitar condição de corrida - duas requisições simultâneas)
    # Recarregar loja_data para pegar atualizações recentes (sem sleep para melhor performance)
    loja_data = db.get_document("loja_data")
    bot_ref = inter.bot if hasattr(inter, 'bot') else None
    existing_cart_id_check, existing_cart_check = await _find_user_open_cart(
        inter.author.id, 
        inter.guild.id, 
        delivery_type, 
        bot=bot_ref, 
        guild=inter.guild,
        loja_data_cache=loja_data  # Usar cache atualizado
    )
    
    if existing_cart_id_check and existing_cart_check:
        # Adicionar produto ao carrinho existente
        updated_cart = await _add_item_to_cart(existing_cart_id_check, product_id, campo_id, quantity, price, loja_data_cache=loja_data)
        
        if not updated_cart:
            # Não conseguiu adicionar (provavelmente falta de estoque)
            # Verificar estoque para dar mensagem apropriada
            stock_count = StockManager.get_available_stock(product_id, campo_id)
            is_infinite = stock_count == 999999
            
            if delivery_type == "automatic" and not is_infinite and stock_count <= 0:
                # Sem estoque disponível - mostrar botão de notificação
                notify_emoji = ensure_emoji(emoji.warn)
                notify_button = disnake.ui.Button(
                    emoji=notify_emoji,
                    label="Receber notificação ao repor estoque",
                    style=disnake.ButtonStyle.grey,
                    custom_id=f"notify_stock:{product_id}:{campo_id}"
                )
                
                if loading_msg:
                    try:
                        await loading_msg.edit(
                            content=f"{emoji.wrong} Sem estoque disponível para este item.",
                            components=[disnake.ui.ActionRow(notify_button)]
                        )
                    except:
                        try:
                            await inter.followup.send(
                                content=f"{emoji.wrong} Sem estoque disponível para este item.",
                                components=[disnake.ui.ActionRow(notify_button)],
                                ephemeral=True
                            )
                        except:
                            pass
                else:
                    try:
                        await inter.edit_original_message(
                            content=f"{emoji.wrong} Sem estoque disponível para este item.",
                            embed=None,
                            components=[disnake.ui.ActionRow(notify_button)]
                        )
                    except (disnake.NotFound, disnake.HTTPException):
                        try:
                            await inter.followup.send(
                                content=f"{emoji.wrong} Sem estoque disponível para este item.",
                                components=[disnake.ui.ActionRow(notify_button)],
                                ephemeral=True
                            )
                        except:
                            pass
                return
            else:
                # Estoque insuficiente para a quantidade solicitada
                items = existing_cart_check.get("items", [])
                total_quantity_in_cart = sum(
                    it.get("quantity", 0) for it in items
                    if it.get("product_id") == product_id and it.get("campo_id") == campo_id
                )
                available_stock = stock_count - total_quantity_in_cart
                
                if loading_msg:
                    try:
                        await loading_msg.edit(
                            content=f"{emoji.wrong} Estoque insuficiente. Disponível: `{available_stock}`, solicitado: `{quantity}`.",
                            components=[]
                        )
                    except:
                        pass
                else:
                    try:
                        await inter.edit_original_message(
                            content=f"{emoji.wrong} Estoque insuficiente. Disponível: `{available_stock}`, solicitado: `{quantity}`.",
                            embed=None,
                            components=[]
                        )
                    except (disnake.NotFound, disnake.HTTPException):
                        try:
                            await inter.followup.send(
                                content=f"{emoji.wrong} Estoque insuficiente. Disponível: `{available_stock}`, solicitado: `{quantity}`.",
                                ephemeral=True
                            )
                        except:
                            pass
                return
        
        if updated_cart:
            # Atualizar delivery_type do carrinho baseado nos produtos
            products = db.get_document("loja_products")
            items = updated_cart.get("items", [])
            delivery_types = set()
            for item in items:
                prod = products.get(item.get("product_id"), {})
                info = prod.get("info") or {}
                item_delivery = info.get("delivery_type", "automatic")
                delivery_types.add(item_delivery)
            
            # Se tem tipos mistos, marcar como "mixed", senão usar o tipo único
            if len(delivery_types) > 1:
                updated_cart["delivery_type"] = "mixed"
            else:
                updated_cart["delivery_type"] = list(delivery_types)[0] if delivery_types else "automatic"
            
            # Salvar carrinho atualizado (reutilizar loja_data)
            loja_data["carts"][existing_cart_id_check] = updated_cart
            db.save_document("loja_data", loja_data)
            
            # Buscar thread
            try:
                thread_id = existing_cart_check.get("thread_id")
                thread = inter.guild.get_thread(thread_id)
                
                if thread:
                    # Atualizar mensagem do carrinho
                    cart_message_id = existing_cart_check.get("cart_message_id")
                    if cart_message_id:
                        try:
                            cart_msg = await thread.fetch_message(cart_message_id)
                            new_cart_msg = await _build_cart_message(updated_cart, thread, mode)
                            await cart_msg.delete()
                            loja_data["carts"][existing_cart_id_check]["cart_message_id"] = new_cart_msg.id
                            db.save_document("loja_data", loja_data)
                        except:
                            try:
                                new_cart_msg = await _build_cart_message(updated_cart, thread, mode)
                                loja_data["carts"][existing_cart_id_check]["cart_message_id"] = new_cart_msg.id
                                db.save_document("loja_data", loja_data)
                            except:
                                pass
                    else:
                        try:
                            new_cart_msg = await _build_cart_message(updated_cart, thread, mode)
                            loja_data["carts"][existing_cart_id_check]["cart_message_id"] = new_cart_msg.id
                            db.save_document("loja_data", loja_data)
                        except:
                            pass
                    
                    try:
                        mention_msg = await thread.send(f"{inter.author.mention} Produto adicionado ao carrinho!")
                        await asyncio.sleep(3)
                        try:
                            await mention_msg.delete()
                        except:
                            pass
                    except:
                        pass
                    
                    await _respond_cart_success(inter, thread, loading_msg, created=False)
                    return
                else:
                    content = f"{emoji.correct} Produto adicionado ao carrinho existente."
                    if loading_msg:
                        try:
                            await loading_msg.edit(content=content, components=[])
                        except Exception:
                            await inter.followup.send(content, ephemeral=True)
                    else:
                        try:
                            await inter.edit_original_message(content=content, embed=None, components=[])
                        except Exception:
                            await inter.followup.send(content, ephemeral=True)
                    return
            except Exception:
                if thread is not None:
                    await _respond_cart_success(inter, thread, loading_msg, created=False)
                else:
                    try:
                        await inter.followup.send(
                            f"{emoji.correct} Produto adicionado ao carrinho existente.",
                            ephemeral=True,
                        )
                    except Exception:
                        pass
                return
        else:
            # Se não conseguiu adicionar, continuar para criar novo carrinho
            pass
    
    try:
        # Obter cargo admin
        cargos_data = db.get_document("cargos")
        cargo_admin_id = cargos_data.get("cargo_admin")
        
        # Nome do tópico - sempre começa com 💱 (pendente)
        # delivery_type já foi obtido acima
        
        # Garantir que product_name não está vazio e limitar tamanho
        safe_product_name = product_name.strip() if product_name else "Produto"
        safe_user_name = inter.author.name[:30] if inter.author.name else "User"
        
        # Sempre começa com 💱 (carrinho pendente)
        thread_name = f"💱・{safe_product_name}・{safe_user_name}"
        
        # Garantir que o nome do tópico tem entre 1 e 100 caracteres
        thread_name = thread_name[:100] if len(thread_name) > 100 else thread_name
        if not thread_name or len(thread_name) < 1:
            thread_name = f"💱・carrinho・{safe_user_name}"
        
        # Criar o tópico no canal de texto atual ou, caso a interação tenha
        # ocorrido dentro de outro tópico, no canal pai desse tópico.
        thread_host = _resolve_cart_thread_host(inter)
        if thread_host is None:
            raise RuntimeError(
                "Não foi possível localizar um canal de texto para criar o carrinho. "
                "Publique o painel em um canal de texto comum ou configure as permissões do bot."
            )

        thread = await thread_host.create_thread(
            name=thread_name,
            auto_archive_duration=60,  # 1 hora
            type=disnake.ChannelType.private_thread,
            invitable=False
        )
        
        # Pequena pausa para garantir que a thread esteja disponível no cache
        await asyncio.sleep(0.2)
        
    except Exception as e:
        # Mensagem administrativa - sempre content simples
        try:
            await inter.edit_original_message(
                content=f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Erro ao criar tópico: {e}",
                embed=None,
                components=[]
            )
        except (disnake.NotFound, disnake.HTTPException):
            # Mensagem não existe mais ou não pode ser editada, enviar nova mensagem
            try:
                await inter.followup.send(
                    content=f"{emoji.wrong if hasattr(emoji, 'error') else '❌'} Erro ao criar tópico: {e}",
                    ephemeral=True
                )
            except:
                pass
        return
    
    # Criar estrutura inicial do carrinho com items
    cart_items = [{
        "product_id": product_id,
        "campo_id": campo_id,
        "quantity": quantity,
        "price_per_unit": price,
        "item_total": price * quantity
    }]
    
    
    # Salvar dados do carrinho ANTES de enviar mensagem (para evitar race condition)
    cart_id = str(thread.id)
    timestamp = int(datetime.utcnow().timestamp())
    
    # Reutilizar loja_data já carregado anteriormente
    if "carts" not in loja_data:
        loja_data["carts"] = {}
    
    # Criar estrutura inicial do carrinho (cart_message_id será atualizado depois)
    cart_data = {
        "cart_id": cart_id,
        "thread_id": thread.id,
        "cart_message_id": None,  # Será atualizado após criar a mensagem
        "channel_id": inter.channel.id,
        "guild_id": inter.guild.id,
        "user_id": inter.author.id,
        "items": cart_items,  # Nova estrutura com array de items
        "total_price": sum(item.get("item_total", 0) for item in cart_items),  # Total sem desconto ainda
        "discount_amount": 0,  # Desconto será aplicado quando continuar
        "coupon_code": None,  # Cupom será aplicado quando continuar
        "coupon_type": None,
        "payment_method": payment_method,  # Método escolhido, mas pagamento ainda não criado
        "payment_data": None,  # Será criado quando clicar em continuar
        "status": "cart",  # Status "cart" = carrinho ainda não foi para pagamento
        "delivery_type": delivery_type,  # Salvar tipo de entrega do carrinho
        "created_at": timestamp,
        "updated_at": timestamp,
        "is_free_purchase": False
    }
    
    
    loja_data["carts"][cart_id] = cart_data
    db.save_document("loja_data", loja_data)
    
    # Enviar mensagem do carrinho (sem pagamento ainda)
    cart_msg = await _build_cart_message(
        {
            "items": cart_items,
            "user_id": inter.author.id,
            "guild_id": inter.guild.id,
            "payment_method": payment_method,
        },
        thread,
        mode
    )
    
    # Atualizar cart_message_id no carrinho salvo (reutilizar loja_data)
    if cart_id in loja_data.get("carts", {}):
        loja_data["carts"][cart_id]["cart_message_id"] = cart_msg.id
        db.save_document("loja_data", loja_data)
    
    # Enviar mensagem marcando o usuário e cargo admin, depois apagar
    # Carregar cargos apenas uma vez (já foi carregado antes, mas reutilizar se possível)
    cargos_data = db.get_document("cargos") or {}
    cargo_admin_id = cargos_data.get("cargo_admin")
    admin_mention = ""
    if cargo_admin_id:
        try:
            role = inter.guild.get_role(int(cargo_admin_id))
            if role:
                admin_mention = f" {role.mention}"
        except Exception:
            pass
    
    mention_msg = await thread.send(f"{inter.author.mention}{admin_mention} Carrinho criado!")
    await asyncio.sleep(3)
    try:
        await mention_msg.delete()
    except:
        pass
    
    await _respond_cart_success(inter, thread, loading_msg, created=True)

    # Enviar DM informando criação do carrinho
    try:
        cart_url = f"https://discord.com/channels/{inter.guild.id}/{thread.id}"
        
        if delivery_type == "manual":
            delivery_text = f"Entrega manual. Ela será realizada no carrinho do servidor."
        else:
            delivery_text = "Entrega automática. Assim que o pagamento for aprovado, você receberá os itens nesta conversa."
        
        if mode == "embed":
            dm_embed = disnake.Embed(
                title=f"{emoji.cart} Carrinho Criado",
                description=(
                    f"**Produto:** `{product_name}`\n"
                    f"**Opção:** `{campo_name}`\n"
                    f"**Quantidade:** `{quantity}`"
                ),
                color=disnake.Color.blurple()
            )
            dm_embed.add_field(
                name=f"Entrega",
                value=delivery_text,
                inline=False
            )
            await inter.author.send(
                embed=dm_embed,
                components=[
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Ir para o carrinho",
                            style=disnake.ButtonStyle.url,
                            emoji=emoji.cart,
                            url=cart_url
                        )
                    )
                ]
            )
        else:
            # Modo Container
            color_data = db.get_document("custom_colors") or {}
            primary_color = color_data.get("primary")
            container_kwargs = {}
            if primary_color:
                container_kwargs["accent_colour"] = disnake.Colour(int(primary_color.replace("#", ""), 16))
            
            await inter.author.send(
                components=[
                    disnake.ui.Container(
                        disnake.ui.TextDisplay(f"# {emoji.cart} Carrinho Criado"),
                        disnake.ui.Separator(),
                        disnake.ui.TextDisplay(
                            f"-# **Produto:** `{product_name}`\n"
                            f"-# **Opção:** `{campo_name}`\n"
                            f"-# **Quantidade:** `{quantity}`"
                        ),
                        disnake.ui.Separator(),
                        disnake.ui.TextDisplay(f"{delivery_text}"),
                        **container_kwargs
                    ),
                    disnake.ui.ActionRow(
                        disnake.ui.Button(
                            label="Ir para o carrinho",
                            style=disnake.ButtonStyle.url,
                            emoji=emoji.cart,
                            url=cart_url
                        )
                    )
                ],
                flags=disnake.MessageFlags(is_components_v2=True)
            )
    except Exception:
        pass


def _sanitize_error_for_user(error_msg: str) -> str:
    """
    Remove informações técnicas de mensagens de erro para exibição ao usuário
    """
    msg = str(error_msg)
    
    # Tentar extrair mensagem de erro de JSON se existir
    try:
        json_match = re.search(r'\{[^{}]*"mensagem"[^{}]*\}', msg, re.IGNORECASE)
        if json_match:
            json_str = json_match.group(0)
            json_data = json.loads(json_str)
            if isinstance(json_data, dict) and "mensagem" in json_data:
                return json_data["mensagem"]
    except:
        pass
    
    # Tentar extrair mensagem de erro de JSON com "message"
    try:
        json_match = re.search(r'\{[^{}]*"message"[^{}]*\}', msg, re.IGNORECASE)
        if json_match:
            json_str = json_match.group(0)
            try:
                json_data = json.loads(json_str)
                if isinstance(json_data, dict):
                    if "message" in json_data:
                        msg_data = json_data["message"]
                        if isinstance(msg_data, dict) and "mensagem" in msg_data:
                            return msg_data["mensagem"]
                        elif isinstance(msg_data, str):
                            return msg_data
            except (json.JSONDecodeError, ValueError):
                pass
    except Exception:
        pass
    
    # Remover URLs (http://, https://)
    msg = re.sub(r'https?://[^\s]+', '', msg)
    
    # Remover rotas de API (ex: /api/v1/create-efi-payment)
    msg = re.sub(r'/api/v\d+/[^\s]+', '', msg)
    msg = re.sub(r'/api/[^\s]+', '', msg)
    
    # Remover códigos HTTP no início (ex: 500, 400)
    msg = re.sub(r'^\d+\s+', '', msg)
    
    # Remover referências a BASE_URL ou URLs específicas
    msg = re.sub(r'pay\.syncapplications\.com\.br[^\s]*', '', msg, flags=re.IGNORECASE)
    
    # Limpar espaços múltiplos
    msg = re.sub(r'\s+', ' ', msg)
    
    # Remover dois pontos duplos ou pontos isolados no início
    msg = re.sub(r'^:\s*', '', msg)
    msg = msg.strip()
    
    return msg


async def _create_payment(
    payment_method: str,
    amount: float,
    user: disnake.Member,
    description: str,
    *,
    cart_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Cria pagamento apenas em provedores configurados e efetivamente suportados."""
    if amount < 0.01:
        raise ValueError(f"Valor muito baixo: R$ {amount:.2f}. O valor mínimo é R$ 0,01")
    if payment_method != "pix":
        raise RuntimeError("A loja está configurada para receber pagamentos por PIX.")

    pagamentos = db.get_document("pagamentos") or {}
    payment_configs = db.get_document("payment_configs") or {}
    errors: list[str] = []

    def _entry(provider: str) -> dict:
        value = payment_configs.get(provider, {})
        return value if isinstance(value, dict) else {"enabled": bool(value)}

    def _enabled(provider: str) -> bool:
        entry = _entry(provider)
        return bool(entry.get("enabled", pagamentos.get(provider, False)))

    async def _attempt(label: str, provider: str, factory):
        if not _enabled(provider) or not should_allow_payment_provider(provider):
            return None
        try:
            result = await factory()
            if not result:
                raise RuntimeError("A integração não retornou os dados da cobrança.")
            result["_provider"] = provider
            return result
        except Exception as exc:
            errors.append(f"{label}: {_sanitize_error_for_user(str(exc))}")
            return None

    # A Carteira Integrada utiliza uma única URL/chave global definida no .env.
    async def _wallet():
        from functions.payments.sync_wallet import (
            create_sync_payment_from_settings,
            global_wallet_is_configured,
        )
        if not global_wallet_is_configured():
            raise ValueError("API global não configurada no ambiente")
        return await create_sync_payment_from_settings(
            value=amount,
            description=description,
            customer_name=(user.display_name if user else "Cliente"),
            customer_external_id=(str(user.id) if user else None),
            metadata={
                "cartId": cart_id,
                "discordUserId": str(user.id) if user else None,
            },
        )

    result = await _attempt("Carteira Integrada", "sync_wallet", _wallet)
    if result:
        return result

    result = await _attempt(
        "Mercado Pago",
        "mercado_pago",
        lambda: create_mp_payment_from_settings(amount),
    )
    if result:
        return result

    result = await _attempt(
        "Efí",
        "efibank",
        lambda: create_efi_payment_from_settings(
            price=amount,
            nome_pagador=user.display_name if user else "Cliente",
        ),
    )
    if result:
        return result

    async def _pushinpay():
        from functions.payments import create_pushinpay_payment_from_settings
        return await create_pushinpay_payment_from_settings(int(round(amount * 100)))

    result = await _attempt("PushinPay", "pushinpay", _pushinpay)
    if result:
        return result

    async def _misticpay():
        payer_name = (user.display_name or user.name or "Cliente") if user else "Cliente"
        payer_document = str(user.id)[:11] if user else "00000000000"
        return await create_misticpay_payment_from_settings(
            amount=amount,
            payer_name=payer_name,
            payer_document=payer_document,
            description=description,
        )

    result = await _attempt("MisticPay", "misticpay", _misticpay)
    if result:
        return result

    result = await _attempt(
        "PIX Manual",
        "pix_manual",
        lambda: create_manual_pix_payment(amount, description=description),
    )
    if result:
        return result

    if errors:
        raise RuntimeError(
            "Nenhum provedor PIX conseguiu criar a cobrança.\n" + "\n".join(errors[:6])
        )
    raise RuntimeError(
        "Nenhuma forma de pagamento PIX está ativa e configurada. "
        "Acesse Configurações > Formas de Pagamento."
    )


async def _monitor_payment(cart_id: str, payment_method: str, payment_ids: Dict[str, str], payment_provider: Optional[str], bot):
    """
    Monitora o status do pagamento usando o provedor correto
    
    Sistema de intervalo progressivo para reduzir carga na API:
    - Primeiros 2 minutos: verifica a cada 10 segundos (12 requisições)
    - Próximos 3 minutos: verifica a cada 20 segundos (9 requisições)
    - Próximos 5 minutos: verifica a cada 30 segundos (10 requisições)
    - Próximos 10 minutos: verifica a cada 60 segundos (10 requisições)
    - Restante (40 minutos): verifica a cada 120 segundos (20 requisições)
    
    Total: ~61 requisições em 60 minutos (vs 720 requisições no sistema antigo)
    Redução de 91% nas requisições!
    """
    try:
        # Definir intervalos progressivos (tempo_limite_segundos, intervalo_segundos)
        intervals = [
            (120, 10),    # 0-2 min: a cada 10s
            (300, 10),    # 2-5 min: a cada 10s
            (600, 20),    # 5-10 min: a cada 20s
            (1200, 30),   # 10-20 min: a cada 30s
            (3600, 60),  # 20-60 min: a cada 60s
        ]
        
        start_time = time.time()
        iteration = 0
        
        while True:
            # Calcular tempo decorrido
            elapsed = time.time() - start_time
            
            # Se passou 60 minutos, parar
            if elapsed >= 3600:
                break
            
            # Determinar intervalo atual baseado no tempo decorrido
            current_interval = 120  # Padrão: 2 minutos
            for time_limit, interval in intervals:
                if elapsed < time_limit:
                    current_interval = interval
                    break
            
            # Aguardar o intervalo apropriado
            await asyncio.sleep(current_interval)
            iteration += 1
            
            # Carregar dados do carrinho
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            
            if not cart:
                return
            
            # Se já foi aprovado ou cancelado, parar
            current_status = cart.get("status")
            if current_status in ["approved", "cancelled", "expired"]:
                return
            
            # Tentar obter provedor do payment_data se não foi passado (fazer ANTES de buscar payment_id)
            if not payment_provider:
                payment_data = cart.get("payment_data", {})
                payment_provider = payment_data.get("payment_provider")
                if not payment_provider and payment_data.get("raw"):
                    payment_provider = payment_data.get("raw", {}).get("_provider")
            
            # Obter ID do pagamento (também tentar do payment_data se não estiver em payment_ids)
            # Priorizar txid se o provedor for efibank
            if payment_provider == "efibank":
                payment_id = (
                    payment_ids.get("txid") or
                    payment_ids.get("payment_id") or
                    payment_ids.get("id")
                )
            else:
                payment_id = (
                    payment_ids.get("payment_id") or
                    payment_ids.get("id") or
                    payment_ids.get("payment_intent") or
                    payment_ids.get("invoice_id") or
                    payment_ids.get("preference_id") or
                    payment_ids.get("charge") or
                    payment_ids.get("txid")
                )
            
            # Se ainda não encontrou, tentar do payment_data
            if not payment_id:
                payment_data = cart.get("payment_data", {})
                raw_data = payment_data.get("raw", {})
                
                # Priorizar txid para Efí
                if payment_provider == "efibank":
                    payment_id = (
                        raw_data.get("txid") or
                        raw_data.get("payment_id") or
                        raw_data.get("id")
                    )
                else:
                    payment_id = (
                        raw_data.get("payment_id") or
                        raw_data.get("id") or
                        raw_data.get("txid") or
                        raw_data.get("payment_intent") or
                        raw_data.get("invoice_id")
                    )
            
            if not payment_id:
                continue
            
            # Verificar status do pagamento usando o provedor correto
            chk = {}
            try:
                # Se temos o provedor, usar diretamente
                if payment_provider:
                    provider_checkers = {
                        "sync_wallet": lambda pid: __import__('functions.payments.sync_wallet', fromlist=['check_sync_payment_from_settings']).check_sync_payment_from_settings(pid),
                        "mercado_pago": check_mp_payment_from_settings,
                        "efibank": check_efi_payment_from_settings,
                        "pagbank": check_pagbank_payment_from_settings,
                        "picpay": check_picpay_payment_from_settings,
                        "pushinpay": check_pushinpay_payment_from_settings,
                        "misticpay": check_misticpay_payment_from_settings,
                        "stripe": check_stripe_payment_from_settings,
                        "paypal": check_paypal_payment_from_settings,
                        "asaas": check_asaas_payment_from_settings,
                        "coinbase": check_coinbase_payment_from_settings,
                        "nowpayments": check_nowpayments_invoice_from_settings,
                        "pix_manual": check_manual_pix_payment,
                    }
                    
                    checker = provider_checkers.get(payment_provider)
                    if checker:
                        try:
                            chk = await checker(payment_id)
                        except Exception:
                            chk = {}
                else:
                    # Se não temos o provedor, tentar todos os disponíveis para o método
                    if payment_method == "pix":
                        # Tentar todos os provedores PIX em ordem de prioridade
                        from functions.payments.sync_wallet import check_sync_payment_from_settings as check_sync
                        pix_providers = [
                            ("sync_wallet", check_sync),
                            ("mercado_pago", check_mp_payment_from_settings),
                            ("efibank", check_efi_payment_from_settings),
                            ("pagbank", check_pagbank_payment_from_settings),
                            ("asaas", check_asaas_payment_from_settings),
                            ("pushinpay", check_pushinpay_payment_from_settings),
                            ("misticpay", check_misticpay_payment_from_settings),
                            ("picpay", check_picpay_payment_from_settings),
                            ("pix_manual", check_manual_pix_payment),
                        ]
                        
                        for provider_name, checker_func in pix_providers:
                            try:
                                chk = await checker_func(payment_id)
                                # Se obteve resposta válida, salvar o provedor
                                if chk:
                                    payment_data = cart.get("payment_data", {})
                                    payment_data["payment_provider"] = provider_name
                                    cart["payment_data"] = payment_data
                                    loja_data["carts"][cart_id] = cart
                                    db.save_document("loja_data", loja_data)
                                    break
                            except Exception:
                                continue
                    
                    elif payment_method == "card":
                        # Tentar todos os provedores de cartão
                        card_providers = [
                            ("stripe", check_stripe_payment_from_settings),
                            ("mercado_pago", check_mp_payment_from_settings),
                            ("asaas", check_asaas_payment_from_settings),
                            ("paypal", check_paypal_payment_from_settings),
                        ]
                        
                        for provider_name, checker_func in card_providers:
                            try:
                                chk = await checker_func(payment_id)
                                if chk:
                                    payment_data = cart.get("payment_data", {})
                                    payment_data["payment_provider"] = provider_name
                                    cart["payment_data"] = payment_data
                                    loja_data["carts"][cart_id] = cart
                                    db.save_document("loja_data", loja_data)
                                    break
                            except Exception:
                                continue
                    
                    elif payment_method == "crypto":
                        # Tentar todos os provedores de crypto
                        crypto_providers = [
                            ("coinbase", check_coinbase_payment_from_settings),
                            ("nowpayments", check_nowpayments_invoice_from_settings),
                        ]
                        
                        for provider_name, checker_func in crypto_providers:
                            try:
                                chk = await checker_func(payment_id)
                                if chk:
                                    payment_data = cart.get("payment_data", {})
                                    payment_data["payment_provider"] = provider_name
                                    cart["payment_data"] = payment_data
                                    loja_data["carts"][cart_id] = cart
                                    db.save_document("loja_data", loja_data)
                                    break
                            except Exception:
                                continue
                
            except Exception:
                chk = {}
            
            # Verificar se foi aprovado
            # Buscar status em vários campos possíveis (incluindo raw do Efí e transaction do MisticPay)
            status = _find_first(chk, ["status", "payment_status", "state", "situacao"]) or "pending"
            
            # Se não encontrou no nível superior, tentar em data.status (Carteira Integrada pode retornar result diretamente)
            if status == "pending" and isinstance(chk, dict):
                data = chk.get("data", {})
                if isinstance(data, dict):
                    data_status = data.get("status")
                    if data_status:
                        status = data_status
            
            # Se não encontrou no nível superior, tentar em raw (Efí retorna em raw.status, MisticPay em raw.transaction.transactionState)
            if status == "pending" and isinstance(chk, dict):
                raw_data = chk.get("raw", {})
                if isinstance(raw_data, dict):
                    # Tentar raw.status primeiro (Efí)
                    raw_status_value = raw_data.get("status")
                    if raw_status_value:
                        status = raw_status_value
                    else:
                        # Tentar raw.transaction.transactionState (MisticPay)
                        transaction = raw_data.get("transaction", {})
                        if isinstance(transaction, dict):
                            transaction_state = transaction.get("transactionState")
                            if transaction_state:
                                status = transaction_state
            
            status_lower = str(status).lower()
            
            # Verificar também o campo "paid" se existir (MisticPay retorna isso)
            is_paid = chk.get("paid", False) if isinstance(chk, dict) else False
            
            # Status aprovados (incluindo "concluida" do Efí e "completo" do MisticPay)
            approved_statuses = {
                "approved", "paid", "completed", "completo", "succeeded", "accredited", 
                "concluida", "concluído", "pago", "aprovado"
            }
            
            # Status cancelados/falhados (incluindo "falha" do MisticPay)
            failed_statuses = {
                "canceled", "cancelled", "expired", "failed", "falha", "removida", 
                "removido", "cancelado", "expirado", "falhou"
            }
            
            # Verificar se foi aprovado: status aprovado OU campo paid=True
            if status_lower in approved_statuses or is_paid:
                # Pagamento aprovado!
                await _handle_payment_approved(cart_id, bot)
                return
            
            elif status_lower in failed_statuses:
                # Pagamento falhou
                cart["status"] = status_lower
                cart["updated_at"] = int(datetime.utcnow().timestamp())
                loja_data["carts"][cart_id] = cart
                db.save_document("loja_data", loja_data)
                return
    
    except Exception:
        pass


async def _check_single_payment_status(
    cart_id: str,
    payment_id: str,
    payment_method: str,
    payment_provider: Optional[str],
    bot
) -> tuple[bool, Optional[str]]:
    """
    Verifica o status de um pagamento individual e retorna se foi aprovado/falhou
    
    Returns:
        (is_finished, status) - is_finished=True se pagamento foi aprovado ou falhou,
                                status indica o status final
    """
    try:
        # Verificar status do pagamento usando o provedor correto
        chk = {}
        
        if payment_provider:
            provider_checkers = {
                "sync_wallet": lambda pid: __import__('functions.payments.sync_wallet', fromlist=['check_sync_payment_from_settings']).check_sync_payment_from_settings(pid),
                "mercado_pago": check_mp_payment_from_settings,
                "efibank": check_efi_payment_from_settings,
                "pagbank": check_pagbank_payment_from_settings,
                "picpay": check_picpay_payment_from_settings,
                "pushinpay": check_pushinpay_payment_from_settings,
                "misticpay": check_misticpay_payment_from_settings,
                "stripe": check_stripe_payment_from_settings,
                "paypal": check_paypal_payment_from_settings,
                "asaas": check_asaas_payment_from_settings,
                "coinbase": check_coinbase_payment_from_settings,
                "nowpayments": check_nowpayments_invoice_from_settings,
                "pix_manual": check_manual_pix_payment,
            }
            
            checker = provider_checkers.get(payment_provider)
            if checker:
                try:
                    chk = await checker(payment_id)
                except Exception as e:
                    print(f"[Check Payment] Erro ao verificar {payment_provider} para cart {cart_id}: {e}")
                    return False, None
        else:
            # Tentar todos os provedores para o método
            if payment_method == "pix":
                from functions.payments.sync_wallet import check_sync_payment_from_settings as check_sync
                pix_providers = [
                    ("sync_wallet", check_sync),
                    ("mercado_pago", check_mp_payment_from_settings),
                    ("efibank", check_efi_payment_from_settings),
                    ("pagbank", check_pagbank_payment_from_settings),
                    ("asaas", check_asaas_payment_from_settings),
                    ("pushinpay", check_pushinpay_payment_from_settings),
                    ("misticpay", check_misticpay_payment_from_settings),
                    ("picpay", check_picpay_payment_from_settings),
                    ("pix_manual", check_manual_pix_payment),
                ]
                
                for provider_name, checker_func in pix_providers:
                    try:
                        chk = await checker_func(payment_id)
                        if chk:
                            payment_provider = provider_name
                            break
                    except Exception:
                        continue
        
        if not chk:
            return False, None
        
        # Extrair status
        status = _find_first(chk, ["status", "payment_status", "state", "situacao"]) or "pending"
        
        # Verificar também em data.status (Carteira Integrada pode retornar result diretamente)
        if status == "pending" and isinstance(chk, dict):
            data = chk.get("data", {})
            if isinstance(data, dict):
                data_status = data.get("status")
                if data_status:
                    status = data_status
        
        # Verificar também em raw
        if status == "pending" and isinstance(chk, dict):
            raw_status = chk.get("raw", {})
            if isinstance(raw_status, dict):
                raw_status_value = raw_status.get("status")
                if raw_status_value:
                    status = raw_status_value
        
        status_lower = str(status).lower()
        is_paid = chk.get("paid", False) if isinstance(chk, dict) else False
        
        # Status aprovados
        approved_statuses = {
            "approved", "paid", "completed", "completo", "succeeded", "accredited", 
            "concluida", "concluído", "pago", "aprovado"
        }
        
        # Status cancelados/falhados
        failed_statuses = {
            "canceled", "cancelled", "expired", "failed", "falha", "removida", 
            "removido", "cancelado", "expirado", "falhou"
        }
        
        if status_lower in approved_statuses or is_paid:
            return True, "approved"
        elif status_lower in failed_statuses:
            return True, status_lower
        
        return False, None
        
    except Exception as e:
        print(f"[Check Payment] Erro ao verificar pagamento para cart {cart_id}: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def _process_free_purchase(cart_id: str, bot):
    """Processa compra gratuita (cupom 100%) automaticamente"""
    # Aguardar 2 segundos para garantir que tudo foi salvo
    await asyncio.sleep(2)
    
    # Processar como pagamento aprovado
    await _handle_payment_approved(cart_id, bot)


async def _handle_payment_approved(cart_id: str, bot):
    """Processa pagamento aprovado"""
    print(f"[CHECKOUT] Iniciando processamento de pagamento aprovado para cart_id: {cart_id}")
    
    try:
        # Carregar dados
        loja_data = db.get_document("loja_data")
        
        cart = loja_data.get("carts", {}).get(cart_id)
        
        if not cart:
            print(f"[CHECKOUT] Carrinho {cart_id} não encontrado!")
            return
        
        # Debug: verificar carrinho antes da migração
        
        if "items" in cart:
            items_raw = cart.get('items')
            if isinstance(items_raw, list) and items_raw:
                for idx, it in enumerate(items_raw):
                    pass
        else:
            pass
        
        # Migrar para estrutura de items se necessário
        cart = _migrate_cart_to_items(cart)
        
        # Debug: verificar carrinho depois da migração
        
        # Verificar se items estão válidos
        items = cart.get("items", [])
        if not items or not any(item.get("product_id") and item.get("campo_id") for item in items):
            # Tentar recarregar do banco de dados
            loja_data = db.get_document("loja_data")
            cart = loja_data.get("carts", {}).get(cart_id)
            if cart:
                cart = _migrate_cart_to_items(cart)
                items = cart.get("items", [])
                if not items or not any(item.get("product_id") and item.get("campo_id") for item in items):
                    return
        
        # SALVAR CARRINHO MIGRADO antes de continuar!
        loja_data["carts"][cart_id] = cart
        db.save_document("loja_data", loja_data)
        
        # Atualizar status
        cart["status"] = "approved"
        cart["approved_at"] = int(datetime.utcnow().timestamp())
        cart["auto_close_at"] = cart["approved_at"] + 180
        cart["updated_at"] = int(datetime.utcnow().timestamp())
        loja_data["carts"][cart_id] = cart
        db.save_document("loja_data", loja_data)
        
        # Deduzir saldo usado (se houver)
        try:
            balance_applied = cart.get("balance_applied", 0)
            balance_user_id = cart.get("balance_user_id")
            if balance_applied > 0 and balance_user_id:
                from modules.loja.saldo.checkout_integration import SaldoCheckoutIntegration
                await SaldoCheckoutIntegration.process_balance_deduction(cart, bot)
        except Exception as e:
            print(f"[CHECKOUT] Erro ao deduzir saldo: {e}")
        
        # Ativar modo rápido no contador de vendas se disponível
        try:
            task_cog = bot.get_cog("ContVendasTaskCog")
            if task_cog and hasattr(task_cog, "trigger_fast_mode"):
                task_cog.trigger_fast_mode(cart["guild_id"])
        except Exception:
            pass
        
        # Buscar thread
        guild = bot.get_guild(cart["guild_id"])
        if not guild:
            print(f"[CHECKOUT] Guild {cart.get('guild_id')} não encontrado!")
            return
        
        thread = guild.get_thread(cart["thread_id"])
        if not thread:
            print(f"[CHECKOUT] Thread {cart.get('thread_id')} não encontrada!")
            return
        
        print(f"[CHECKOUT] Thread encontrada: {thread.name}")

        # Esta mensagem só é enviada depois que o provedor confirma o pagamento.
        # Ela funciona como status temporário e será editada quando a entrega terminar.
        approval_progress_msg = None
        try:
            approval_progress_msg = await thread.send(
                f"{emoji.correct} Compra aprovada com sucesso, entregando produtos..."
            )
            cart["approval_progress_message_id"] = approval_progress_msg.id
            loja_data["carts"][cart_id] = cart
            db.save_document("loja_data", loja_data)
        except Exception as progress_error:
            print(f"[CHECKOUT] Não foi possível enviar o status de aprovação: {progress_error}")
        
        # NOTA: A mensagem de pagamento (QR code) será deletada mais abaixo
        # A mensagem do carrinho será atualizada mais abaixo também
        
        # Enviar mensagem de sucesso e processar entrega
        # Resolver usuário com fallback (cache -> fetch_member -> fetch_user)
        user = guild.get_member(cart["user_id"])
        if not user:
            try:
                user = await guild.fetch_member(int(cart["user_id"]))
            except Exception:
                try:
                    user = await bot.fetch_user(int(cart["user_id"]))
                except Exception:
                    user = None

        # Abrir a DM antecipadamente para entregar o produto e gerar o botão direto.
        purchase_dm_channel = None
        if user:
            try:
                purchase_dm_channel = user.dm_channel or await user.create_dm()
            except Exception as dm_error:
                print(f"[CHECKOUT] Não foi possível abrir a DM do comprador: {dm_error}")

        # Atribuir cargo de cliente após pagamento aprovado (apenas para Member)
        cargo_atribuido = False
        try:
            cargos_cfg = db.get_document("cargos") or {}
            cliente_role_id = cargos_cfg.get("cargo_cliente")
            if cliente_role_id and isinstance(user, disnake.Member):
                role = guild.get_role(int(cliente_role_id))
                if role and role not in user.roles:
                    await user.add_roles(role, reason="Compra aprovada - cargo cliente")
                    cargo_atribuido = True
        except Exception:
            pass
        
        # Marcar usuário no canal de feedback após receber cargo de cliente
        if cargo_atribuido and user:
            try:
                canais = db.get_document("canais") or {}
                feedback_channel_id = canais.get("canal_de_feedback")
                if feedback_channel_id:
                    feedback_channel = guild.get_channel(int(feedback_channel_id))
                    if feedback_channel:
                        # Enviar mensagem marcando o usuário
                        feedback_msg = await feedback_channel.send(f"{user.mention}")
                        # Apagar a mensagem imediatamente após enviar
                        await feedback_msg.delete()
            except Exception:
                pass

        # Obter tipo de entrega e items ANTES de usar
        delivery_type = cart.get("delivery_type", "automatic")
        products = db.get_document("loja_products")
        items = cart.get("items", [])

        # Prozynexa a aplicação/licença no ZYNEX Manager sem bloquear a entrega.
        schedule_manager_notification(cart_id, cart, products, user)
        
        # Enviar notificação WhatsApp (Fire and Forget)
        try:
             # Calcular total final
             total_val = sum(item.get("item_total", 0) for item in items)
             disc = cart.get("discount_amount", 0) or 0
             bal = cart.get("balance_applied", 0) or 0
             total_val = max(0, total_val - disc - bal)
             
             # Nome do produto
             first_prod_id = items[0].get("product_id") if items else None
             first_prod_name = products.get(first_prod_id, {}).get("name", "Produto") if first_prod_id else "Produto"
             if len(items) > 1:
                 p_name_str = f"{first_prod_name} + {len(items)-1} itens"
             else:
                 p_name_str = first_prod_name
             
             b_name = user.display_name if user else "Cliente"
             
             # Executar em background para não bloquear
             asyncio.create_task(_send_whatsapp_notification(
                 product_name=p_name_str,
                 value=f"R$ {total_val:,.2f}",
                 buyer_name=b_name
             ))
        except Exception as e:
            print(f"[WhatsApp] Falha ao preparar notificação: {e}")
        
        # Inicializar variáveis de controle de entrega (disponíveis em todo o escopo)
        manual_items = []
        automatic_items = []
        all_delivered = True
        delivered_automatically = False
        
        # Separar itens por tipo de entrega ANTES de processar (independente de user)
        if items:
            for item in items:
                product_id = item.get("product_id")
                campo_id = item.get("campo_id")
                qty = item.get("quantity", 1)
                
                if not product_id or not campo_id:
                    all_delivered = False
                    continue
                
                product = products.get(product_id, {})
                if not product:
                    all_delivered = False
                    continue
                
                # Obter tipo de entrega deste produto específico
                info = product.get("info") or {}
                item_delivery_type = info.get("delivery_type", "automatic")
                
                product_name = product.get("name", "Produto")
                campos = product.get("campos") or {}
                field = campos.get(campo_id, {})
                campo_name = field.get("name", "") if field else ""
                
                if item_delivery_type == "automatic":
                    automatic_items.append({
                        "product_id": product_id,
                        "campo_id": campo_id,
                        "product_name": product_name,
                        "campo_name": campo_name,
                        "quantity": qty,
                        "item": item
                    })
                else:
                    manual_items.append({
                        "product_id": product_id,
                        "campo_id": campo_id,
                        "product_name": product_name,
                        "campo_name": campo_name,
                        "quantity": qty,
                        "item": item
                    })
        
        # Debug: verificar items
        if items:
            for idx, item in enumerate(items):
                pass

        try:
            # A confirmação pública fica no carrinho. A DM é reservada para o produto,
            # o comprovante e a avaliação, evitando mensagens duplicadas.

            # Armazenar itens entregues para logs (chave: (product_id, campo_id))
            delivered_items_map = {}
            
            # Processar entrega para cada item individualmente (suporta tipos mistos)
            if user:
                try:
                    # Processar entrega automática para itens automáticos
                    # (manual_items e automatic_items já foram separados acima)
                    for auto_item in automatic_items:
                        try:
                            # NOTA: NÃO retirar estoque aqui! O process_automatic_delivery
                            # já retira o estoque internamente. Retirar aqui causava
                            # o bug de "produto não encontrado" por duplicação.
                            
                            item_delivered = await process_automatic_delivery(
                                user=user,
                                product_id=auto_item["product_id"],
                                campo_id=auto_item["campo_id"],
                                product_name=auto_item["product_name"],
                                campo_name=auto_item["campo_name"],
                                quantity=auto_item["quantity"],
                                thread=thread,
                                guild=guild
                            )
                            
                            if item_delivered:
                                # Marcar como entregue para o log
                                key = (auto_item["product_id"], auto_item["campo_id"])
                                # O estoque já foi retirado dentro de process_automatic_delivery
                                # Marcamos apenas que foi entregue com sucesso
                                delivered_items_map[key] = True
                            else:
                                all_delivered = False
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            print(f"[Delivery Error] Erro ao entregar item {auto_item.get('product_name')}: {e}")
                            all_delivered = False
                            # Remover da lista se falhou
                            key = (auto_item["product_id"], auto_item["campo_id"])
                            delivered_items_map.pop(key, None)
                            # Continuar com próximo item mesmo se este falhar
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[Delivery Error] Erro geral no processamento de entrega: {e}")
                
                # Para itens manuais, apenas registrar que precisam de entrega manual
                # Itens manuais serão concluídos pela equipe diretamente na DM
                
                # Aplicar cargos dos produtos (adicionar e remover)
                try:
                    for item in items:
                        product_id = item.get("product_id")
                        campo_id = item.get("campo_id")
                        
                        if not product_id or not campo_id:
                            continue
                        
                        product = products.get(product_id, {})
                        if not product:
                            continue
                        
                        campos = product.get("campos") or {}
                        field = campos.get(campo_id, {})
                        if not field:
                            continue
                        
                        # Obter configuração de cargos da opção
                        cargos_config = field.get("cargos", {})
                        roles_to_add = cargos_config.get("adicionar", [])
                        roles_to_remove = cargos_config.get("remover", [])
                        duracao_minutos = cargos_config.get("duracao_minutos")
                        
                        # Adicionar cargos
                        if roles_to_add:
                            for role_id in roles_to_add:
                                try:
                                    role = guild.get_role(int(role_id))
                                    if role and role not in user.roles:
                                        await user.add_roles(role, reason=f"Compra do produto: {product.get('name', 'Produto')}")
                                        
                                        # Se o cargo tem duração, registrar em roles_temp
                                        if duracao_minutos and duracao_minutos > 0:
                                            roles_temp = db.get_document("loja_roles_temp") or {}
                                            expiration_time = int(time.time()) + (duracao_minutos * 60)
                                            
                                            user_id_str = str(user.id)
                                            if user_id_str not in roles_temp:
                                                roles_temp[user_id_str] = []
                                            
                                            # Adicionar cargo temporário
                                            roles_temp[user_id_str].append({
                                                "role_id": role.id,
                                                "expires_at": expiration_time,
                                                "guild_id": guild.id
                                            })
                                            db.save_document("loja_roles_temp", roles_temp)
                                except (ValueError, TypeError):
                                    pass
                                except disnake.Forbidden:
                                    print(f"[CHECKOUT] ⚠️ Sem permissão para adicionar cargo {role_id} ao usuário {user.id}")
                                    pass
                                except Exception as e:
                                    print(f"[CHECKOUT] ⚠️ Erro ao adicionar cargo {role_id}: {e}")
                                    pass
                        
                        # Remover cargos
                        if roles_to_remove:
                            for role_id in roles_to_remove:
                                try:
                                    role = guild.get_role(int(role_id))
                                    if role and role in user.roles:
                                        await user.remove_roles(role, reason=f"Compra do produto: {product.get('name', 'Produto')}")
                                except (ValueError, TypeError):
                                    pass
                                except disnake.Forbidden:
                                    print(f"[CHECKOUT] ⚠️ Sem permissão para remover cargo {role_id} do usuário {user.id}")
                                    pass
                                except Exception as e:
                                    print(f"[CHECKOUT] ⚠️ Erro ao remover cargo {role_id}: {e}")
                                    pass
                except Exception as e:
                    print(f"[CHECKOUT] ⚠️ Erro geral ao aplicar cargos: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continuar mesmo se houver erro ao aplicar cargos
                
                # delivered_automatically = True apenas se todos os itens automáticos foram entregues
                # e não há itens manuais (ou se há itens manuais, eles serão entregues no carrinho)
                delivered_automatically = all_delivered and len(automatic_items) > 0 and len(manual_items) == 0
            else:
                # Se não tem user, não pode entregar automaticamente
                delivered_automatically = False
                # Mas ainda precisa calcular manual_items_count corretamente
                # (já foi calculado acima antes do if user)
            
            # Renomear thread após pagamento aprovado (independente de ter user ou não)
            # ✅ se todos os produtos são automáticos e foram entregues
            # ⌚ se há algum produto de entrega manual
            if thread:
                try:
                    old_name = thread.name
                    new_name = None
                    
                    # Verificar se há produtos de entrega manual
                    if len(manual_items) > 0:
                        # Se há itens manuais, usar ⌚
                        if old_name.startswith("💱・"):
                            new_name = old_name.replace("💱・", "⌚・", 1)
                        elif old_name.startswith("✅・"):
                            new_name = old_name.replace("✅・", "⌚・", 1)
                    else:
                        # Se não há itens manuais, usar ✅
                        if old_name.startswith("💱・"):
                            new_name = old_name.replace("💱・", "✅・", 1)
                        elif old_name.startswith("⌚・"):
                            new_name = old_name.replace("⌚・", "✅・", 1)
                    
                    if new_name:
                        await thread.edit(name=new_name)
                except Exception as e:
                    pass
            
            # Registrar compra no histórico para cada item (sempre, independente do tipo de entrega)
            registered_purchase_ids = []
            if user and items:
                    try:
                        discount_amount = float(cart.get("discount_amount", 0))
                        total_cart_price = float(cart.get("total_price", 0))
                        
                        # Registrar cada item separadamente
                        for item in items:
                            product_id = item.get("product_id")
                            campo_id = item.get("campo_id")
                            qty = item.get("quantity", 1)
                            unit_price = item.get("price_per_unit", 0)
                            item_total = item.get("item_total", 0)
                            
                            product = products.get(product_id, {})
                            product_name = product.get("name", "Produto")
                            campos = product.get("campos") or {}
                            field = campos.get(campo_id) or {}
                            campo_name = field.get("name", "")
                            
                            # Obter tipo de entrega específico deste item
                            info = product.get("info") or {}
                            item_delivery_type = info.get("delivery_type", "automatic")
                            
                            # Dividir desconto proporcionalmente entre itens
                            item_discount = (discount_amount * item_total / total_cart_price) if total_cart_price > 0 else 0
                            item_final_price = item_total - item_discount
                            
                            purchase_id = PurchaseManager.register_purchase(
                                user_id=user.id,
                                product_id=product_id,
                                product_name=product_name,
                                field_id=campo_id,
                                field_name=campo_name,
                                quantity=qty,
                                unit_price=unit_price,
                                total_price=item_total,
                                discount_amount=item_discount,
                                final_price=item_final_price,
                                payment_method=cart.get("payment_method", "unknown"),
                                coupon_code=cart.get("coupon_code"),
                                items_received=[],
                                metadata={
                                    "cart_id": cart_id,
                                    "thread_id": cart.get("thread_id"),
                                    "guild_id": cart.get("guild_id"),  # Adicionar guild_id diretamente
                                    "delivery_type": item_delivery_type,
                                    "referral_code": cart.get("referral_code"),
                                    "review_enabled": True,
                                }
                            )

                            # Regras pós-pagamento: comissão de indicação, VIP, comprovante e recomendações.
                            try:
                                from modules.loja.post_payment import process_approved_purchase
                                await process_approved_purchase(
                                    bot=bot,
                                    user=user,
                                    purchase_id=purchase_id,
                                    product_id=product_id,
                                    paid_value=item_final_price,
                                    referral_code=cart.get("referral_code"),
                                    thread=thread,
                                )
                            except Exception as post_error:
                                print(f"[CHECKOUT] Falha em regra pós-pagamento: {post_error}")

                            # Comprovante e avaliação na mesma DM usada para a entrega.
                            try:
                                from modules.loja.purchase_experience import send_purchase_dm
                                item_was_delivered = (
                                    item_delivery_type == "automatic"
                                    and bool(delivered_items_map.get((product_id, campo_id)))
                                )
                                purchase_dm_channel = await send_purchase_dm(
                                    user=user,
                                    purchase_id=purchase_id,
                                    product_name=product_name,
                                    field_name=campo_name,
                                    quantity=qty,
                                    paid_value=item_final_price,
                                    delivered=item_was_delivered,
                                ) or purchase_dm_channel
                                registered_purchase_ids.append(str(purchase_id))
                            except Exception as purchase_notice_error:
                                print(f"[CHECKOUT] Falha ao enviar confirmação da compra: {purchase_notice_error}")
                            
                            # Verificar e atribuir condecorações após compra
                            try:
                                clientes_cog = bot.get_cog("ClientesSystem")
                                if clientes_cog and hasattr(clientes_cog, "check_user_decorations"):
                                    guild = bot.get_guild(int(cart.get("guild_id")))
                                    if guild:
                                        asyncio.create_task(clientes_cog.check_user_decorations(user.id, guild))
                            except Exception as e:
                                print(f"Erro ao verificar condecorações após compra: {e}")
                            
                            # Atualizar vendas do produto (purchasesIds e total_paid)
                            if product_id in products:
                                product_info = products[product_id].get("info", {})
                                purchases_ids = product_info.get("purchasesIds", [])
                                if purchase_id not in purchases_ids:
                                    purchases_ids.append(purchase_id)
                                product_info["purchasesIds"] = purchases_ids
                                product_info["total_paid"] = product_info.get("total_paid", 0) + item_final_price
                                products[product_id]["info"] = product_info
                                db.save_document("loja_products", products)
                                
                                # Sincronizar mensagens do produto para atualizar vendas
                                try:
                                    from modules.loja.products.product.edit import sync_product_messages_silently
                                    asyncio.create_task(sync_product_messages_silently(bot, product_id))
                                except Exception as e:
                                    pass
                        
                        # Marcar cupom como usado se houver (apenas se não for compra gratuita, pois já foi marcado)
                        if cart.get("coupon_code") and cart.get("coupon_type") != "referral" and not cart.get("is_free_purchase"):
                            try:
                                coupon_type = cart.get("coupon_type")
                                # Para cupons globais, usar o primeiro produto; para específicos, usar o produto do cupom
                                first_product_id = items[0].get("product_id") if items else None
                                if coupon_type and first_product_id:
                                    CouponValidator.use_coupon(cart.get("coupon_code"), coupon_type, first_product_id, user.id)
                            except Exception as e:
                                pass
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        print(f"Erro ao registrar compras: {e}")
                        pass

            # A mensagem única de pagamento aprovado será criada abaixo, com botão para a DM.

            # Enviar logs de pedido e evento de compra para cada item (sempre, independente do tipo de entrega)
            if user:
                try:
                    from .stock_manager import StockManager
                    logs_cog = bot.get_cog("PurchaseLogsSystem")
                    
                    if logs_cog:
                        # Enviar logs para cada item
                        for item in items:
                            product_id = item.get("product_id")
                            campo_id = item.get("campo_id")
                            qty = item.get("quantity", 1)
                            item_total = item.get("item_total", 0)
                            
                            product = products.get(product_id, {})
                            product_name = product.get("name", "Produto")
                            campos = product.get("campos") or {}
                            field = campos.get(campo_id) or {}
                            campo_name = field.get("name", "")
                            
                            # Obter tipo de entrega específico deste item
                            info = product.get("info") or {}
                            item_delivery_type = info.get("delivery_type", "automatic")
                            
                            # Obter itens entregues se for entrega automática
                            log_items = None
                            if item_delivery_type == "automatic":
                                key = (product_id, campo_id)
                                log_items = delivered_items_map.get(key)
                            
                            # Enviar log detalhado de pedido para este item
                            await logs_cog.send_order_log(
                                guild=guild,
                                user=user,
                                product_name=product_name,
                                campo_name=campo_name,
                                quantity=qty,
                                price=float(item_total),
                                payment_method=cart.get("payment_method", "unknown"),
                                items=log_items,
                                delivery_type=item_delivery_type,
                                cart_id=cart_id
                            )
                        
                        # Preparar lista de itens para o evento de compra (uma única imagem)
                        event_items = []
                        for item in items:
                            product_id = item.get("product_id")
                            campo_id = item.get("campo_id")
                            qty = item.get("quantity", 1)
                            item_total = item.get("item_total", 0)
                            
                            product = products.get(product_id, {})
                            product_name = product.get("name", "Produto")
                            campos = product.get("campos") or {}
                            field = campos.get(campo_id) or {}
                            campo_name = field.get("name", "")
                            
                            event_items.append({
                                "product_name": product_name,
                                "campo_name": campo_name,
                                "quantity": qty,
                                "price": float(item_total),
                                "product_id": product_id
                            })
                        
                        # Enviar evento público de compra uma única vez com todos os itens
                        final_price = max(0, total_cart_price - discount_amount - balance_applied)
                        await logs_cog.send_purchase_event_bulk(
                            guild=guild,
                            user=user,
                            items=event_items,
                            total_price=final_price,
                            subtotal=total_cart_price,
                            discount_amount=discount_amount if discount_amount > 0 else None,
                            coupon_code=cart.get("coupon_code")
                        )
                except Exception as e:
                    print(f"[CHECKOUT] ERRO ao enviar logs de pedido/evento: {e}")
                    import traceback
                    traceback.print_exc()
            
            # DELETAR mensagem do pagamento (QR code) sempre, independente do tipo de entrega
            print(f"[CHECKOUT] Tentando deletar mensagem de pagamento...")
            try:
                payment_message_id = cart.get("message_id")
                print(f"[CHECKOUT] payment_message_id: {payment_message_id}")
                if payment_message_id:
                    try:
                        payment_msg = await thread.fetch_message(payment_message_id)
                        await payment_msg.delete()
                        print(f"[CHECKOUT] ✅ Mensagem de pagamento {payment_message_id} deletada com sucesso")
                    except disnake.NotFound:
                        print(f"[CHECKOUT] ⚠️ Mensagem de pagamento {payment_message_id} não encontrada (já foi deletada?)")
                    except Exception as e:
                        print(f"[CHECKOUT] ❌ Erro ao deletar mensagem de pagamento: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[CHECKOUT] ⚠️ Nenhuma mensagem de pagamento encontrada no carrinho")
            except Exception as e:
                print(f"[CHECKOUT] ❌ Erro geral ao deletar mensagem de pagamento: {e}")
                import traceback
                traceback.print_exc()
            
            # DELETAR mensagem do carrinho APENAS se for entrega automática
            # Se houver itens manuais, manter a mensagem do carrinho para referência
            if len(manual_items) == 0:  # Só deletar se não houver itens manuais
                try:
                    cart_message_id = cart.get("cart_message_id")
                    if cart_message_id:
                        try:
                            cart_msg = await thread.fetch_message(cart_message_id)
                            await cart_msg.delete()
                            print(f"[CHECKOUT] Mensagem do carrinho {cart_message_id} deletada")
                        except disnake.NotFound:
                            print(f"[CHECKOUT] Mensagem do carrinho {cart_message_id} não encontrada")
                        except Exception as e:
                            print(f"[CHECKOUT] Erro ao deletar mensagem do carrinho: {e}")
                except Exception as e:
                    print(f"[CHECKOUT] Erro ao deletar mensagem do carrinho: {e}")
            else:
                print(f"[CHECKOUT] Mantendo mensagem do carrinho (há {len(manual_items)} itens manuais)")
            
            # Aplicar cashback ao saldo do usuário
            try:
                from modules.loja.cashback.manager import CashbackManager
                if user and CashbackManager.is_enabled():
                    # Obter valor final pago (após descontos e saldo)
                    total_price = sum(item.get("item_total", 0) for item in items)
                    discount_amount = cart.get("discount_amount", 0) or 0
                    balance_applied = cart.get("balance_applied", 0) or 0
                    final_price = max(0, total_price - discount_amount - balance_applied)
                    
                    # Obter roles do usuário
                    user_roles = []
                    if isinstance(user, disnake.Member):
                        user_roles = [role.id for role in user.roles]
                    
                    # Calcular e aplicar cashback
                    cashback_amount = CashbackManager.calculate_cashback(final_price, user_roles)
                    if cashback_amount > 0:
                        success, message = CashbackManager.apply_cashback(
                            user.id,
                            cashback_amount,
                            purchase_ref=cart_id
                        )
                        if success:
                            print(f"[CHECKOUT] Cashback de R$ {cashback_amount:.2f} creditado ao usuário {user.id}")
                        else:
                            print(f"[CHECKOUT] Erro ao creditar cashback: {message}")
            except Exception as e:
                print(f"[CHECKOUT] Erro ao processar cashback: {e}")
            
            # Contar itens manuais para determinar se mostrar botão
            # manual_items foi inicializado acima no escopo da função
            manual_items_count = len(manual_items) if manual_items else 0
            
            # Finalizar a mesma mensagem enviada no momento da aprovação.
            # Evita criar embeds extras no carrinho e mantém o fluxo igual à referência.
            try:
                if approval_progress_msg is None:
                    progress_id = cart.get("approval_progress_message_id")
                    if progress_id:
                        try:
                            approval_progress_msg = await thread.fetch_message(int(progress_id))
                        except Exception:
                            approval_progress_msg = None

                close_at = int(cart.get("auto_close_at") or (int(datetime.utcnow().timestamp()) + 180))
                final_components = []
                if purchase_dm_channel:
                    final_components.append(
                        disnake.ui.ActionRow(
                            disnake.ui.Button(
                                label="Ir para o pedido entregue",
                                style=disnake.ButtonStyle.url,
                                url=f"https://discord.com/channels/@me/{purchase_dm_channel.id}",
                            )
                        )
                    )

                if delivered_automatically:
                    final_content = (
                        f"Entrega realizada! Verifique seu privado, esse carrinho será excluído "
                        f"<t:{close_at}:R>"
                    )
                elif len(manual_items) > 0:
                    final_content = (
                        f"Pagamento aprovado! A entrega será concluída pela equipe na sua DM. "
                        f"Este carrinho será excluído <t:{close_at}:R>"
                    )
                else:
                    final_content = (
                        f"Pagamento aprovado, mas a entrega não foi concluída automaticamente. "
                        f"Ative sua DM e procure o suporte."
                    )

                if approval_progress_msg:
                    await approval_progress_msg.edit(
                        content=final_content,
                        embed=None,
                        components=final_components or None,
                    )
                    cart["approved_message_id"] = approval_progress_msg.id
                else:
                    new_msg = await thread.send(
                        content=final_content,
                        components=final_components or None,
                    )
                    cart["approved_message_id"] = new_msg.id

                loja_data["carts"][cart_id] = cart
                db.save_document("loja_data", loja_data)
                print("[CHECKOUT] ✅ Status de aprovação/entrega atualizado no carrinho")
            except Exception as e:
                print(f"[CHECKOUT] ❌ Erro ao atualizar status de aprovação/entrega: {e}")
                import traceback
                traceback.print_exc()

            # Mensagens no tópico conforme resultado
            # Obter cargo admin uma vez (fora do if user para garantir que sempre seja mencionado)
            print(f"[CHECKOUT] Preparando mensagens no tópico...")
            cargos_data = db.get_document("cargos")
            cargo_admin_id = cargos_data.get("cargo_admin")
            admin_mention = ""
            try:
                if cargo_admin_id:
                    role = guild.get_role(int(cargo_admin_id))
                    if role:
                        admin_mention = f" {role.mention}"
                        print(f"[CHECKOUT] Cargo admin encontrado: {role.name}")
                    else:
                        print(f"[CHECKOUT] ⚠️ Cargo admin {cargo_admin_id} não encontrado no servidor")
                else:
                    print(f"[CHECKOUT] ⚠️ Nenhum cargo admin configurado")
            except Exception as e:
                print(f"[CHECKOUT] Erro ao obter cargo admin: {e}")
            
            try:
                if user:
                    if delivered_automatically:
                        print(f"[CHECKOUT] ✅ Produto entregue por DM; fechamento automático agendado")
                    else:
                        # Entrega manual ou parcial: mencionar admins
                        if len(manual_items) > 0:
                            print(f"[CHECKOUT] Enviando mensagem de entrega manual para {len(manual_items)} itens")
                            # Avisar que itens de entrega manual aguardam entrega por admin
                            products_list = []
                            for manual_item in manual_items:
                                product_name = manual_item.get("product_name", "Produto")
                                campo_name = manual_item.get("campo_name", "Opção")
                                qty = manual_item.get("quantity", 1)
                                products_list.append(f"{emoji.arrow} **{product_name}** - `{campo_name}` (x{qty})")
                            
                            products_text = "\n".join(products_list)
                            
                            msg_content = f"{emoji.warn} **Itens de entrega manual aguardando entrega.**{admin_mention}\n\n{products_text}"
                            await thread.send(msg_content)
                            print(f"[CHECKOUT] ✅ Mensagem de entrega manual enviada com menção de admins")
                        elif not delivered_automatically:
                            # Se não há itens manuais mas também não foi entregue automaticamente (erro na entrega automática)
                            await thread.send(
                                f"{emoji.warn} **Houve um problema na entrega automática.** Por favor, entre em contato com um administrador.{admin_mention}"
                            )
                            print(f"[CHECKOUT] ⚠️ Mensagem de erro na entrega automática enviada")
                else:
                    # Se não tem user mas há itens manuais, ainda precisa mencionar admins
                    if len(manual_items) > 0:
                        print(f"[CHECKOUT] Enviando mensagem de entrega manual (sem user) para {len(manual_items)} itens")
                        products_list = []
                        for manual_item in manual_items:
                            product_name = manual_item.get("product_name", "Produto")
                            campo_name = manual_item.get("campo_name", "Opção")
                            qty = manual_item.get("quantity", 1)
                            products_list.append(f"{emoji.arrow} **{product_name}** - `{campo_name}` (x{qty})")
                        
                        products_text = "\n".join(products_list)
                        
                        msg_content = f"{emoji.warn} **Itens de entrega manual aguardando entrega.**{admin_mention}\n\n{products_text}"
                        await thread.send(msg_content)
                        print(f"[CHECKOUT] ✅ Mensagem de entrega manual enviada (sem user)")
            except Exception as e:
                print(f"[CHECKOUT] ❌ Erro ao enviar mensagens no tópico: {e}")
                import traceback
                traceback.print_exc()

            # Gerar e enviar transcript se habilitado (antes de deletar)
            try:
                from modules.loja.preferences.generate_transcript import generate_cart_transcript, send_cart_transcript_to_channel
                prefs = db.get_document("loja_preferences") or {}
                if prefs.get("transcript_enabled", False):
                    transcript_channel_id = prefs.get("transcript_channel_id")
                    if transcript_channel_id:
                        transcript_file = await generate_cart_transcript(thread, bot, cart)
                        if transcript_file:
                            await send_cart_transcript_to_channel(bot, transcript_file, int(transcript_channel_id), cart)
            except Exception as e:
                print(f"Erro ao gerar transcript: {e}")
                import traceback
                traceback.print_exc()
            
            # Fechar e bloquear o carrinho exatamente três minutos após a aprovação.
            close_delay = max(0, int(cart.get("auto_close_at", int(time.time()) + 180) - time.time()))
            asyncio.create_task(_close_approved_cart_later(thread, cart_id, close_delay))
            
            print(f"[CHECKOUT] Processamento de pagamento aprovado concluído para cart_id: {cart_id}")
        except Exception as e:
            import traceback
            print(f"[CHECKOUT] Erro no processamento de pagamento aprovado (dentro do try principal): {e}")
            traceback.print_exc()
        
    except Exception as e:
        import traceback
        print(f"[CHECKOUT] Erro crítico no processamento de pagamento aprovado: {e}")
        traceback.print_exc()
