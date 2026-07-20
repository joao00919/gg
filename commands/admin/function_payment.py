import asyncio
import base64
import io
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import disnake
from disnake.ext import commands
import aiohttp

from functions.message import message, embed_message
from functions.database import database as db
from functions.emoji import emoji
from functions.utils import utils
from functions.perms import perms

from functions.payments import (
    create_mp_payment_from_settings,
    create_mp_site_payment_from_settings,
    create_efi_payment_from_settings,
    create_pagbank_payment_from_settings,
    create_picpay_payment_from_settings,
    create_pushinpay_payment_from_settings,
    create_stripe_payment_from_settings,
    create_paypal_payment_from_settings,
    create_asaas_payment_link_from_settings,
    create_asaas_pix_payment_from_settings,
    create_coinbase_payment_from_settings,
    create_nowpayments_invoice_from_settings,
    create_manual_pix_payment,
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
)
from functions.payments.create_payment import BASE_URL as PAY_API_BASE
from functions.database import database as db
from modules.loja.cart.purchase_manager import PurchaseManager
from functions.payments.misticpay import (
    create_misticpay_payment_from_settings,
    check_misticpay_payment_from_settings,
)
from functions.payments.sync_wallet import (
    check_sync_payment_from_settings,
)
from functions.plan import is_free, should_allow_payment_provider
from functions.promotions import get_effective_price
from modules.loja.cart.stock_manager import StockManager
from modules.loja.cart.delivery import deliver_product_to_user


def _generate_valid_cpf() -> str:
    """Gera um CPF válido aleatório."""
    def calculate_digit(cpf_partial: List[int], weight_start: int) -> int:
        total = sum(cpf_partial[i] * (weight_start - i) for i in range(len(cpf_partial)))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder
    
    # Gera os 9 primeiros dígitos aleatoriamente
    cpf_digits = [random.randint(0, 9) for _ in range(9)]
    
    # Calcula o primeiro dígito verificador
    first_digit = calculate_digit(cpf_digits, 10)
    cpf_digits.append(first_digit)
    
    # Calcula o segundo dígito verificador
    second_digit = calculate_digit(cpf_digits, 11)
    cpf_digits.append(second_digit)
    
    # Retorna o CPF como string
    return ''.join(map(str, cpf_digits))


def _load_config() -> Dict[str, Any]:
    """Carrega configurações de pagamento do database"""
    return db.get_document("payment_configs") or {}


def _load_payments() -> Dict[str, Any]:
    """Carrega rastreamento de pagamentos do database"""
    return db.get_document("payment_tracking") or {"items": {}}


def _save_payments(data: Dict[str, Any]) -> None:
    """Salva rastreamento de pagamentos no database"""
    db.save_document("payment_tracking", data)


def _providers_all() -> List[Tuple[str, str]]:
    return [
        ("sync_wallet", "Carteira Integrada"),
        ("mercado_pago", "Mercado Pago"),
        ("efibank", "EfiBank"),
        ("misticpay", "MisticPay"),
        ("pushinpay", "PushinPay"),
        ("pix_manual", "PIX Manual"),
    ]


def _configured_providers() -> List[str]:
    cfg = _load_config()
    configured: List[str] = []
    def has(x: Optional[str]) -> bool:
        return bool(x and str(x).strip())
    # Mercado Pago
    if has((cfg.get("mercado_pago") or {}).get("access_token")):
        configured.append("mercado_pago")
    # EfiBank
    efi = cfg.get("efibank") or {}
    if has(efi.get("client_id") or efi.get("client")) and has(efi.get("client_secret") or efi.get("token")) and has(efi.get("pix_key")) and has(efi.get("cert_file")) and Path(str(efi.get("cert_file"))).exists():
        configured.append("efibank")
    # MisticPay
    mp = cfg.get("misticpay") or {}
    if has(mp.get("client_id")) and has(mp.get("client_secret")):
        configured.append("misticpay")
    # PagBank
    if has((cfg.get("pagbank") or {}).get("token_pagbank")):
        configured.append("pagbank")
    # PicPay
    if has((cfg.get("picpay") or {}).get("token_picpay")):
        configured.append("picpay")
    # PushinPay
    if has((cfg.get("pushinpay") or {}).get("token_pushinpay")):
        configured.append("pushinpay")
    # Stripe
    if has((cfg.get("stripe") or {}).get("token_stripe")):
        configured.append("stripe")
    # PayPal
    p = cfg.get("paypal") or {}
    if has(p.get("client_id")) and has(p.get("client_secret")):
        configured.append("paypal")
    # Asaas
    if has((cfg.get("asaas") or {}).get("token_asaas")):
        configured.append("asaas")
    # Coinbase
    if has((cfg.get("coinbase") or {}).get("token_coinbase")):
        configured.append("coinbase")
    # NOWPayments
    if has((cfg.get("nowpayments") or {}).get("token_nowpayments")):
        configured.append("nowpayments")
    # Carteira Integrada: credencial global definida pelo operador no .env.
    from functions.payments.sync_wallet import global_wallet_is_configured
    if global_wallet_is_configured():
        configured.append("sync_wallet")
    # PIX Manual
    pm = cfg.get("pix_manual") or {}
    if has(pm.get("pix_key")) and has(pm.get("pix_key_type")):
        configured.append("pix_manual")
    return configured


def _find_first(data: Any, keys: List[str]) -> Optional[Any]:
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


def _extract_urls(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    checkout = _find_first(data, [
        "checkout_url",
        "url",
        "init_point",
        "init_url",
        "invoice_url",
        "payment_url",
        "hosted_url",
        "ticket_url",
        "link",
        "redirect_url",
    ])
    copy_code = _find_first(data, [
        "copy_paste",
        "pix_copia_cola",
        "emv",
        "code",
        "qr_code_text",
        "qrcode_text",
    ])
    return str(checkout) if checkout else None, str(copy_code) if copy_code else None


def _extract_qr_image(data: Dict[str, Any]) -> Tuple[Optional[bytes], Optional[str]]:
    # Primeiro tentar qr_code_bytes direto (PIX Manual, PushinPay, PagBank)
    qr_bytes = _find_first(data, ["qr_code_bytes"])
    if isinstance(qr_bytes, bytes):
        return qr_bytes, None
    
    # Tentar base64
    b64 = _find_first(data, [
        "qr_code_base64",
        "qrcode_base64",
        "qr_base64",
        "base64",
    ])
    if isinstance(b64, str):
        try:
            if b64.startswith("data:") and "," in b64:
                b64 = b64.split(",", 1)[1]
            raw = base64.b64decode(b64)
            return raw, "qrcode.png"
        except Exception:
            pass
    
    # Tentar URL
    url = _find_first(data, ["qr_code_url", "qrcode_url", "qr_url", "image", "qr_code_image", "qr_code_image_url"])
    return None, str(url) if url else None


def _api_base_root() -> str:
    base = PAY_API_BASE.rstrip("/")
    if "/api/" in base:
        return base.split("/api/", 1)[0]
    return base


async def _http_get_bytes(url: str, timeout: int = 15) -> Optional[bytes]:
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
    out: Dict[str, str] = {}
    for k in ["payment_id", "id", "payment_intent", "charge", "preference_id", "invoice_id"]:
        v = _find_first(data, [k])
        if v:
            out[k] = str(v)
    return out


def _status_approved(status: str) -> bool:
    s = status.lower()
    return s in {"approved", "paid", "completed", "succeeded", "accredited", "completo"}


def _status_final_failed(status: str) -> bool:
    s = status.lower()
    return s in {"canceled", "cancelled", "expired", "failed", "refunded", "chargeback"}


class PaymentCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def produto_autocomplete(self, inter: disnake.AppCmdInter, string: str) -> List[disnake.OptionChoice]:
        """Lista produtos e variações diretamente no autocomplete do /gerarpix."""
        products = db.get_document("loja_products") or {}
        query = (string or "").strip().lower()
        choices: List[disnake.OptionChoice] = []

        for product_id, product in sorted(
            products.items(), key=lambda item: str((item[1] or {}).get("name", "")).lower()
        ):
            if not isinstance(product, dict):
                continue
            product_name = str(product.get("name") or "Produto").strip()
            campos = product.get("campos") or {}
            if not isinstance(campos, dict) or not campos:
                continue

            for campo_id, campo in campos.items():
                if not isinstance(campo, dict):
                    continue
                campo_name = str(campo.get("name") or "Padrão").strip()
                label = product_name if len(campos) == 1 else f"{product_name} — {campo_name}"
                haystack = f"{product_name} {campo_name} {product_id} {campo_id}".lower()
                if query and query not in haystack:
                    continue
                value = f"{product_id}|{campo_id}"
                choices.append(disnake.OptionChoice(name=label[:100], value=value[:100]))
                if len(choices) >= 25:
                    return choices
        return choices

    @staticmethod
    def _format_brl(value: float) -> str:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _resolve_product_choice(choice: str) -> Tuple[Optional[str], Optional[str], Optional[dict], Optional[dict]]:
        products = db.get_document("loja_products") or {}
        raw = str(choice or "").strip()
        product_id, separator, campo_id = raw.partition("|")
        product = products.get(product_id)
        if not isinstance(product, dict):
            return None, None, None, None
        campos = product.get("campos") or {}
        if not separator:
            if len(campos) != 1:
                return product_id, None, product, None
            campo_id, campo = next(iter(campos.items()))
            return product_id, str(campo_id), product, campo if isinstance(campo, dict) else None
        campo = campos.get(campo_id)
        if not isinstance(campo, dict):
            return product_id, campo_id, product, None
        return product_id, campo_id, product, campo

    async def _finish_product_sale(self, rec_id: str, rec: dict, payment_id: str) -> Tuple[bool, Optional[str]]:
        """Entrega, registra e anuncia uma venda feita pelo /gerarpix."""
        sale = rec.get("sale") or {}
        if not sale:
            return True, None
        if rec.get("sale_processed"):
            return True, None

        products = db.get_document("loja_products") or {}
        product_id = str(sale.get("product_id") or "")
        campo_id = str(sale.get("campo_id") or "")
        product = products.get(product_id) or {}
        campo = (product.get("campos") or {}).get(campo_id) or {}
        if not product or not campo:
            return False, "O produto ou a opção selecionada não existe mais. Faça a entrega manualmente."

        user_id = int(rec.get("user_id") or 0)
        user = self.bot.get_user(user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except Exception:
                user = None
        if user is None:
            return False, "Não foi possível localizar o comprador para realizar a entrega."

        quantity = max(1, int(sale.get("quantity") or 1))
        product_name = str(product.get("name") or sale.get("product_name") or "Produto")
        campo_name = str(campo.get("name") or sale.get("field_name") or "Padrão")
        info = product.get("info") or {}
        delivery_type = str(info.get("delivery_type") or sale.get("delivery_type") or "automatic")
        items_received: List[str] = []

        if delivery_type == "automatic":
            stock_items = StockManager.get_stock_items(product_id, campo_id, quantity)
            if stock_items is None:
                return False, "Pagamento aprovado, mas não há estoque suficiente. O pedido ficou aguardando entrega manual."
            instructions = campo.get("instructions")
            delivered = await deliver_product_to_user(
                user=user,
                product_name=product_name,
                campo_name=campo_name,
                quantity=quantity,
                items=stock_items,
                guild=self.bot.get_guild(int(rec.get("guild_id") or 0)),
                instructions=instructions,
                product_id=product_id,
                campo_id=campo_id,
            )
            if not delivered:
                StockManager.return_stock_items(product_id, campo_id, stock_items)
                return False, "Pagamento aprovado, mas a DM do comprador está fechada. O estoque foi devolvido."
            items_received = stock_items
        else:
            try:
                manual_embed = disnake.Embed(
                    title=f"{emoji.correct} Pagamento aprovado",
                    description=(
                        f"{emoji.cardbox} **Produto:** {product_name}\n"
                        f"{emoji.settings2} **Opção:** {campo_name}\n"
                        f"{emoji.cart} **Quantidade:** {quantity}\n\n"
                        f"{emoji.time} A entrega deste produto é manual. A equipe realizará o atendimento."
                    ),
                    color=disnake.Color.green(),
                )
                await user.send(embed=manual_embed)
            except Exception:
                pass

        unit_price = float(sale.get("unit_price") or 0)
        final_price = float(sale.get("final_price") or rec.get("amount") or 0)
        purchase_id = PurchaseManager.register_purchase(
            user_id=user.id,
            product_id=product_id,
            product_name=product_name,
            field_id=campo_id,
            field_name=campo_name,
            quantity=quantity,
            unit_price=unit_price,
            total_price=final_price,
            discount_amount=0,
            final_price=final_price,
            payment_method="Carteira Integrada",
            items_received=items_received,
            metadata={
                "source": "gerarpix",
                "payment_id": payment_id,
                "idempotency_key": f"gerarpix:{payment_id}",
                "guild_id": rec.get("guild_id"),
                "channel_id": rec.get("channel_id"),
                "delivery_type": delivery_type,
                "review_enabled": True,
            },
        )

        # Atualiza vendas e faturamento exibidos no painel do produto.
        latest_products = db.get_document("loja_products") or {}
        latest_product = latest_products.get(product_id) or product
        latest_info = latest_product.setdefault("info", {})
        purchase_ids = latest_info.setdefault("purchasesIds", [])
        if purchase_id not in purchase_ids:
            purchase_ids.append(purchase_id)
        latest_info["total_paid"] = float(latest_info.get("total_paid") or 0) + final_price
        latest_products[product_id] = latest_product
        db.save_document("loja_products", latest_products)

        try:
            from modules.loja.post_payment import process_approved_purchase
            await process_approved_purchase(
                bot=self.bot,
                user=user,
                purchase_id=purchase_id,
                product_id=product_id,
                paid_value=final_price,
                thread=None,
            )
        except Exception as exc:
            print(f"[GERARPIX] Regra pós-pagamento não concluída: {exc}")

        try:
            from modules.loja.purchase_experience import send_purchase_dm, send_thread_delivery_notice
            dm_channel = await send_purchase_dm(
                user=user,
                purchase_id=purchase_id,
                product_name=product_name,
                field_name=campo_name,
                quantity=quantity,
                paid_value=final_price,
                delivered=(delivery_type == "automatic" and bool(items_received)),
            )
            source_channel = self.bot.get_channel(int(rec.get("channel_id") or 0))
            if source_channel:
                await send_thread_delivery_notice(
                    thread=source_channel,
                    user=user,
                    dm_channel=dm_channel,
                    purchase_ids=[str(purchase_id)],
                    delivered=(delivery_type == "automatic" and bool(items_received)),
                )
        except Exception as exc:
            print(f"[GERARPIX] Confirmação/avaliação não enviada: {exc}")

        try:
            from modules.loja.products.product.edit import sync_product_messages_silently
            asyncio.create_task(sync_product_messages_silently(self.bot, product_id))
        except Exception:
            pass

        guild = self.bot.get_guild(int(rec.get("guild_id") or 0))
        logs_cog = self.bot.get_cog("PurchaseLogsSystem")
        if guild and logs_cog:
            try:
                await logs_cog.send_order_log(
                    guild=guild,
                    user=user,
                    product_name=product_name,
                    campo_name=campo_name,
                    quantity=quantity,
                    price=final_price,
                    payment_method="pix",
                    items=items_received,
                    delivery_type=delivery_type,
                    cart_id=purchase_id,
                )
                await logs_cog.send_purchase_event(
                    guild=guild,
                    user=user,
                    product_name=product_name,
                    campo_name=campo_name,
                    quantity=quantity,
                    price=final_price,
                    product_id=product_id,
                )
            except Exception as exc:
                print(f"[GERARPIX] Não foi possível enviar os anúncios da venda: {exc}")

        rec["sale_processed"] = True
        rec["purchase_id"] = purchase_id
        return True, None

    @commands.Cog.listener("on_button_click")
    async def on_payment_button(self, inter: disnake.MessageInteraction):
        custom_id = str(getattr(inter.component, "custom_id", "") or "")
        if not custom_id.startswith("gerarpix_copy:"):
            return
        token = custom_id.split(":", 1)[1]
        payments = _load_payments()
        record = next(
            (item for item in (payments.get("items") or {}).values() if str(item.get("copy_token")) == token),
            None,
        )
        if not record or not record.get("copy_code"):
            return await inter.response.send_message(
                f"{emoji.wrong} Esta cobrança não está mais disponível.", ephemeral=True
            )
        allowed = inter.author.id in {
            int(record.get("user_id") or 0),
            int(record.get("created_by") or 0),
        }
        if not allowed and not getattr(inter.author.guild_permissions, "administrator", False):
            return await inter.response.send_message(
                f"{emoji.wrong} Você não pode copiar o PIX desta cobrança.", ephemeral=True
            )
        await inter.response.send_message(str(record["copy_code"]), ephemeral=True)

    @commands.slash_command(
        name="gerarpix",
        description="🪙 | Vendas | Gere uma cobrança",
        guild_ids=[utils.obter_server_principal()],
    )
    async def gerarpix(
        self,
        inter: disnake.AppCmdInter,
        valor: Optional[float] = commands.Param(
            default=None,
            description="Valor a cobrar (use para valor livre, sem produto)",
            gt=0,
        ),
        produto: Optional[str] = commands.Param(
            default=None,
            description="Produto a vender; ao ser pago gera uma venda real (entrega + anúncio)",
            autocomplete=produto_autocomplete,
        ),
        quantidade: Optional[int] = commands.Param(
            default=None,
            description="Quantidade do produto (obrigatório ao vender um produto)",
            ge=1,
            le=99,
        ),
        usuario: Optional[disnake.Member] = commands.Param(
            default=None,
            description="Comprador que recebe o produto (obrigatório ao vender um produto)",
        ),
    ):
        if not await perms.check(inter):
            return await embed_message.error(
                inter, "Você não tem permissão para usar este comando.", send=True
            )

        wallet_cfg = ((_load_config().get("sync_wallet") or {}))
        if not isinstance(wallet_cfg, dict) or not wallet_cfg.get("enabled", False):
            return await embed_message.error(
                inter,
                "Ative a Carteira Integrada em `/botconfig` antes de gerar uma cobrança.",
                send=True,
            )

        from functions.payments.sync_wallet import (
            create_sync_payment_from_settings,
            global_wallet_is_configured,
        )
        if not global_wallet_is_configured():
            return await embed_message.error(
                inter,
                "A chave global da PurinCash não foi configurada no `.env`.",
                send=True,
            )

        if bool(valor) == bool(produto):
            return await embed_message.error(
                inter,
                "Informe apenas `valor` para uma cobrança livre ou apenas `produto` para uma venda.",
                send=True,
            )

        buyer = usuario or inter.author
        sale: Optional[dict] = None
        amount: float
        description: str

        if produto:
            if usuario is None or quantidade is None:
                return await embed_message.error(
                    inter,
                    "Ao vender um produto, informe também `quantidade` e `usuario`.",
                    send=True,
                )
            product_id, campo_id, product_data, campo_data = self._resolve_product_choice(produto)
            if not product_id or not campo_id or not product_data or not campo_data:
                return await embed_message.error(
                    inter,
                    "Produto ou opção inválida. Selecione o item pelo autocomplete.",
                    send=True,
                )
            unit_price = float(get_effective_price(product_data, campo_data) or 0)
            if unit_price <= 0:
                return await embed_message.error(
                    inter, "O produto selecionado não possui um preço válido.", send=True
                )
            qty = int(quantidade)
            delivery_type = str((product_data.get("info") or {}).get("delivery_type") or "automatic")
            if delivery_type == "automatic":
                available = StockManager.get_available_stock(product_id, campo_id)
                if available < qty:
                    return await embed_message.error(
                        inter,
                        f"Estoque insuficiente. Disponível: `{available}` unidade(s).",
                        send=True,
                    )
            amount = round(unit_price * qty, 2)
            product_name = str(product_data.get("name") or "Produto")
            field_name = str(campo_data.get("name") or "Padrão")
            description = f"{product_name} — {field_name} x{qty}"
            sale = {
                "product_id": product_id,
                "campo_id": campo_id,
                "product_name": product_name,
                "field_name": field_name,
                "quantity": qty,
                "unit_price": unit_price,
                "final_price": amount,
                "delivery_type": delivery_type,
            }
        else:
            amount = round(float(valor or 0), 2)
            description = f"Cobrança gerada por {inter.author.display_name}"

        await inter.response.defer(with_message=True, ephemeral=False)
        try:
            data = await create_sync_payment_from_settings(
                amount,
                description=description,
                customer_name=buyer.display_name,
                customer_external_id=str(buyer.id),
                metadata={
                    "source": "gerarpix",
                    "guildId": str(inter.guild_id or ""),
                    "channelId": str(inter.channel_id or ""),
                    "buyerId": str(buyer.id),
                    "productId": sale.get("product_id") if sale else None,
                    "fieldId": sale.get("campo_id") if sale else None,
                    "quantity": sale.get("quantity") if sale else None,
                },
            )
        except Exception as exc:
            return await embed_message.error(
                inter, f"Não foi possível gerar o PIX: {str(exc)[:400]}"
            )

        checkout_url, copy_code = _extract_urls(data or {})
        qr_bytes, qr_url = _extract_qr_image(data or {})
        ids = _extract_payment_ids(data or {})
        if not copy_code:
            return await embed_message.error(
                inter, "A PurinCash não retornou o código PIX copia e cola."
            )

        if qr_url:
            full_url = str(qr_url)
            if full_url.startswith("/"):
                full_url = _api_base_root() + full_url
            fetched = await _http_get_bytes(full_url)
            if fetched:
                qr_bytes = fetched

        colors = db.get_document("custom_colors") or {}
        embed_color = disnake.Color.blurple()
        try:
            if colors.get("primary"):
                embed_color = disnake.Color(int(str(colors["primary"]).replace("#", ""), 16))
        except Exception:
            pass

        embed = disnake.Embed(color=embed_color)
        avatar_url = getattr(getattr(buyer, "display_avatar", None), "url", None)
        embed.set_author(name=buyer.display_name, icon_url=avatar_url)
        safe_code = str(copy_code)
        if len(safe_code) > 990:
            safe_code = safe_code[:987] + "..."
        embed.add_field(name="Código copia e cola", value=f"```{safe_code}```", inline=False)
        if sale:
            embed.set_footer(
                text=(
                    f"{sale['product_name']} • {sale['field_name']} • "
                    f"{sale['quantity']}x • {self._format_brl(amount)}"
                )[:2048]
            )
        else:
            embed.set_footer(text=f"Cobrança livre • {self._format_brl(amount)}")

        copy_token = str(inter.id)
        buttons = [
            disnake.ui.Button(
                label="Copiar código",
                emoji=emoji.pix,
                style=disnake.ButtonStyle.grey,
                custom_id=f"gerarpix_copy:{copy_token}",
            )
        ]
        if checkout_url:
            buttons.append(
                disnake.ui.Button(
                    label="Abrir pagamento",
                    emoji=emoji.wallet,
                    style=disnake.ButtonStyle.url,
                    url=str(checkout_url),
                )
            )
        components = [disnake.ui.ActionRow(*buttons)]

        files = None
        if qr_bytes:
            file = disnake.File(io.BytesIO(qr_bytes), filename="qrcode.png")
            embed.set_image(url="attachment://qrcode.png")
            files = [file]

        if files:
            await inter.edit_original_message(content=None, embed=embed, components=components, files=files)
        else:
            await inter.edit_original_message(content=None, embed=embed, components=components)

        msg = await inter.original_message()
        payments = _load_payments()
        payments.setdefault("items", {})
        rec_id = str(msg.id)
        payments["items"][rec_id] = {
            "message_id": msg.id,
            "channel_id": msg.channel.id,
            "guild_id": msg.guild.id if msg.guild else inter.guild_id,
            "user_id": buyer.id,
            "created_by": inter.author.id,
            "provider": "sync_wallet",
            "method_label": "Carteira Integrada",
            "amount": amount,
            "description": description,
            "status": "pending",
            "checkout_url": checkout_url,
            "copy_code": str(copy_code),
            "copy_token": copy_token,
            "qr_url": qr_url,
            "ids": ids,
            "sale": sale,
            "raw": data,
        }
        _save_payments(payments)
        asyncio.create_task(self._monitor_payment(rec_id))

    async def _monitor_payment(self, rec_id: str):
        try:
            for _ in range(180):
                await asyncio.sleep(10)
                payments = _load_payments()
                rec = (payments.get("items") or {}).get(rec_id)
                if not rec:
                    return
                if rec.get("status") in {"approved", "paid", "completed"}:
                    return
                key = rec.get("provider")
                pid = rec.get("ids") or {}
                payment_id = pid.get("payment_id") or pid.get("id") or pid.get("payment_intent") or pid.get("invoice_id")
                if not payment_id:
                    continue
                try:
                    if key == "mercado_pago":
                        chk = await check_mp_payment_from_settings(payment_id)
                    elif key == "efibank":
                        chk = await check_efi_payment_from_settings(payment_id)
                    elif key == "misticpay":
                        chk = await check_misticpay_payment_from_settings(payment_id)
                    elif key == "pagbank":
                        chk = await check_pagbank_payment_from_settings(payment_id)
                    elif key == "picpay":
                        chk = await check_picpay_payment_from_settings(payment_id)
                    elif key == "pushinpay":
                        chk = await check_pushinpay_payment_from_settings(payment_id)
                    elif key == "stripe":
                        chk = await check_stripe_payment_from_settings(payment_id)
                    elif key == "paypal":
                        chk = await check_paypal_payment_from_settings(payment_id)
                    elif key == "asaas_link" or key == "asaas_pix":
                        chk = await check_asaas_payment_from_settings(payment_id)
                    elif key == "coinbase":
                        chk = await check_coinbase_payment_from_settings(payment_id)
                    elif key == "nowpayments":
                        chk = await check_nowpayments_invoice_from_settings(payment_id)
                    elif key == "pix_manual":
                        chk = await check_manual_pix_payment(payment_id)
                    elif key == "sync_wallet":
                        chk = await check_sync_payment_from_settings(payment_id)
                    else:
                        chk = {}
                except Exception:
                    chk = {}
                status = _find_first(chk, ["status", "payment_status", "state"]) or "pending"
                if isinstance(status, str) and _status_approved(status):
                    rec["status"] = "approved"
                    payments["items"][rec_id] = rec
                    _save_payments(payments)
                    
                    # Cobrança de produto: entrega, registra e anuncia uma venda real.
                    # Cobrança livre: registra como pagamento genérico.
                    payment_id = rec.get("ids", {}).get("payment_id") or rec.get("ids", {}).get("id") or str(rec_id)
                    try:
                        if rec.get("sale"):
                            completed, pending_reason = await self._finish_product_sale(rec_id, rec, str(payment_id))
                            if not completed:
                                rec["status"] = "approved_pending_delivery"
                                rec["pending_reason"] = pending_reason
                            payments["items"][rec_id] = rec
                            _save_payments(payments)
                        else:
                            PurchaseManager.register_generic_payment(
                                user_id=rec.get("user_id"),
                                amount=rec.get("amount") or 0,
                                payment_method=rec.get("method_label") or "Carteira Integrada",
                                description=rec.get("description") or "Cobrança livre",
                                payment_id=str(payment_id),
                                metadata={
                                    "source": "gerarpix",
                                    "message_id": rec_id,
                                    "channel_id": rec.get("channel_id"),
                                    "guild_id": rec.get("guild_id"),
                                    "idempotency_key": f"gerarpix:{payment_id}",
                                },
                            )
                    except Exception as e:
                        rec["status"] = "approved_pending_delivery"
                        rec["pending_reason"] = str(e)[:500]
                        payments["items"][rec_id] = rec
                        _save_payments(payments)
                        print(f"Erro ao finalizar cobrança /gerarpix: {e}")
                    
                    chan = self.bot.get_channel(rec.get("channel_id"))
                    if chan:
                        try:
                            msg = await chan.fetch_message(int(rec_id))
                            embed = msg.embeds[0] if msg.embeds else disnake.Embed(title="Pagamento")
                            embed.color = disnake.Color.green()
                            if rec.get("status") == "approved_pending_delivery":
                                embed.add_field(
                                    name="Status",
                                    value=f"{emoji.warn} Pagamento aprovado — entrega aguardando atendimento",
                                    inline=False,
                                )
                            else:
                                embed.add_field(name="Status", value=f"{emoji.correct} Aprovado", inline=False)
                            try:
                                embed.set_image(url=None)
                            except Exception:
                                pass
                            await msg.edit(embed=embed, components=[], attachments=[])
                        except Exception:
                            pass
                    try:
                        u = self.bot.get_user(rec.get("user_id"))
                        if u:
                            url = f"https://discord.com/channels/{rec.get('guild_id')}/{rec.get('channel_id')}/{rec_id}"
                            amount = rec.get("amount") or 0
                            amount_str = f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            title = f"Pagamento - {rec.get('method_label') or 'Pagamento'}"
                            desc = rec.get("description") or ""
                            dm_embed = disnake.Embed(title=title, description=desc, color=disnake.Color.green())
                            dm_embed.add_field(name="Valor", value=amount_str, inline=True)
                            dm_embed.add_field(name="Status", value=f"{emoji.correct} Aprovado", inline=False)
                            dm_row = disnake.ui.ActionRow(
                                disnake.ui.Button(label="Ir para a Mensagem", style=disnake.ButtonStyle.url, url=url)
                            )
                            await u.send(embed=dm_embed, components=[dm_row])
                    except Exception:
                        pass
                    return
                if isinstance(status, str) and _status_final_failed(status):
                    rec["status"] = status
                    payments["items"][rec_id] = rec
                    _save_payments(payments)
                    return
        except Exception:
            return


def setup(bot: commands.Bot):
    bot.add_cog(PaymentCog(bot))