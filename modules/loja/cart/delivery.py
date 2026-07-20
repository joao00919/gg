"""
Sistema de entrega automática de produtos.
"""
import disnake
import io
from typing import List, Optional
from functions.emoji import emoji
from functions.database import database as db
from .stock_manager import StockManager


def _create_stock_file(items: List[str]) -> disnake.File:
    """Cria um arquivo TXT com os itens entregues."""
    content = "\n".join(str(item) for item in items)
    file_buffer = io.BytesIO(content.encode("utf-8"))
    file_buffer.seek(0)
    return disnake.File(file_buffer, filename="produto_liberado.txt")



def _delivery_color() -> disnake.Colour:
    colors = db.get_document("custom_colors") or {}
    raw = str(colors.get("primary") or "").strip().replace("#", "")
    try:
        return disnake.Colour(int(raw, 16)) if raw else disnake.Colour(0x5865F2)
    except Exception:
        return disnake.Colour(0x5865F2)

def _money(value: float) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cache_delivery_for_user(user_id: int, product_name: str, items: List[str]) -> None:
    cache = db.get_document("loja_delivery_cache") or {}
    if not isinstance(cache, dict):
        cache = {}
    entries = cache.get("items")
    if not isinstance(entries, dict):
        entries = {}
    entries[str(user_id)] = {
        "product_name": str(product_name or "Produto"),
        "content": "\n".join(str(item) for item in items)[:5000],
    }
    cache["items"] = entries
    db.save_document("loja_delivery_cache", cache)


async def _send_delivery_payload(
    destination,
    *,
    user: disnake.User,
    product_name: str,
    campo_name: str,
    quantity: int,
    items: List[str],
    instructions: Optional[str],
    product_id: Optional[str],
    campo_id: Optional[str],
    is_cart_thread: bool,
    order_reference: Optional[object] = None,
) -> None:
    """Envia o produto no estilo profissional das referências."""
    quantity_value = max(1, int(quantity or 1))
    delivered_count = len(items)
    raw_items = "\n".join(str(item) for item in items)
    preview_items = raw_items[:350] + ("..." if len(raw_items) > 350 else "")
    use_file = len(raw_items) > 900 or delivered_count > 1

    _cache_delivery_for_user(int(user.id), product_name, items)

    description = "Seu produto foi anexado a essa mensagem" if use_file else "Seu produto foi entregue nesta DM"
    embed = disnake.Embed(
        title="Entrega Realizada",
        description=description,
        color=_delivery_color(),
        timestamp=disnake.utils.utcnow(),
    )
    details = f"`{quantity_value}x {product_name}`"
    if campo_name and str(campo_name).strip().lower() not in {"padrão", "padrao", "opção", "opcao"}:
        details += f" • `{campo_name}`"
    embed.add_field(name="Detalhes", value=details[:1024], inline=False)
    if not use_file:
        embed.add_field(name="Produto Liberado", value=f"```\n{preview_items or 'Conteúdo não informado'}\n```"[:1024], inline=False)
    if instructions:
        shown = str(instructions)
        if len(shown) > 1024:
            shown = shown[:1021] + "..."
        embed.add_field(name="Instruções", value=shown, inline=False)

    embed.set_footer(text="ZYNEX Systems • Guarde os dados do produto em local seguro")

    copy_button = disnake.ui.Button(
        label="Copiar Produto",
        emoji="📋",
        style=disnake.ButtonStyle.blurple,
        custom_id=f"delivery_copy:{user.id}",
    )
    components = [disnake.ui.ActionRow(copy_button)]

    kwargs = {
        "embed": embed,
        "components": components,
    }
    if is_cart_thread:
        kwargs["content"] = user.mention
    elif use_file:
        kwargs["content"] = f"**Entrega das Compras**\n\n{product_name} ({quantity_value}x):\n{preview_items or 'Produto entregue no arquivo abaixo.'}"
    if use_file:
        kwargs["file"] = _create_stock_file(items)
    await destination.send(**kwargs)


async def deliver_product_to_user(
    user: disnake.User,
    product_name: str,
    campo_name: str,
    quantity: int,
    items: List[str],
    thread: Optional[disnake.Thread] = None,
    guild: Optional[disnake.Guild] = None,
    instructions: Optional[str] = None,
    product_id: Optional[str] = None,
    campo_id: Optional[str] = None,
) -> bool:
    """Entrega o produto exclusivamente na DM do comprador.

    Dados sensíveis do produto nunca são publicados no carrinho.
    """
    try:
        dm = user.dm_channel or await user.create_dm()
        await _send_delivery_payload(
            dm,
            user=user,
            product_name=product_name,
            campo_name=campo_name,
            quantity=quantity,
            items=items,
            instructions=instructions,
            product_id=product_id,
            campo_id=campo_id,
            is_cart_thread=False,
            order_reference=getattr(thread, "id", None),
        )
        # A avaliação é aberta pelo botão "Avaliar Produto" da própria entrega.
        return True
    except disnake.Forbidden:
        if thread:
            try:
                await thread.send(
                    f"{emoji.wrong} {user.mention}, não consegui enviar o produto na sua DM. "
                    "Ative as mensagens diretas do servidor e procure a equipe para receber a entrega."
                )
            except Exception:
                pass
        return False
    except Exception as exc:
        if thread:
            try:
                await thread.send(
                    f"{emoji.wrong} **Erro na entrega por DM**\n"
                    f"Não foi possível entregar o produto automaticamente: `{str(exc)[:300]}`"
                )
            except Exception:
                pass
        return False


async def _send_feedback_incentive(user: disnake.User, guild: Optional[disnake.Guild]):
    """Mantido para compatibilidade; a avaliação agora abre pelo botão da entrega."""
    return None


async def process_automatic_delivery(
    user: disnake.User,
    product_id: str,
    campo_id: str,
    product_name: str,
    campo_name: str,
    quantity: int,
    thread: Optional[disnake.Thread] = None,
    guild: Optional[disnake.Guild] = None,
) -> bool:
    """Retira o estoque e entrega o produto automaticamente na DM."""
    available_stock = StockManager.get_available_stock(product_id, campo_id)
    items = StockManager.get_stock_items(product_id, campo_id, quantity)

    if items is None:
        if thread:
            embed = disnake.Embed(
                title=f"{emoji.wrong} Estoque Insuficiente",
                description=(
                    "Não há estoque suficiente para entregar este produto.\n"
                    "Entre em contato com um administrador."
                ),
                color=disnake.Color.red(),
            )
            await thread.send(embed=embed)
        return False

    products = db.get_document("loja_products") or {}
    product = products.get(product_id, {}) or {}
    campo = (product.get("campos") or {}).get(campo_id, {}) or {}
    instructions = campo.get("instructions")

    success = await deliver_product_to_user(
        user=user,
        product_name=product_name,
        campo_name=campo_name,
        quantity=quantity,
        items=items,
        thread=thread,
        guild=guild,
        instructions=instructions,
        product_id=product_id,
        campo_id=campo_id,
    )

    if not success:
        try:
            StockManager.add_stock_items(product_id, campo_id, items)
        except Exception:
            print(
                f"[ENTREGA] Falha ao devolver {len(items)} item(ns) ao estoque "
                f"de {product_id}/{campo_id}. Estoque anterior: {available_stock}."
            )
    return success


async def send_payment_approved_dm(
    user: disnake.User,
    product_name: str,
    campo_name: str,
    quantity: int,
    value: float,
    delivered: bool,
) -> bool:
    """Compatibilidade com fluxos antigos de confirmação por DM."""
    try:
        dm = user.dm_channel or await user.create_dm()
        status = "Entregue" if delivered else "Aguardando entrega"
        embed = disnake.Embed(
            title="✅ Pagamento Aprovado!",
            description="Seu pagamento foi processado com sucesso!",
            color=disnake.Color.green(),
            timestamp=disnake.utils.utcnow(),
        )
        embed.add_field(
            name="📋 Informações da Compra",
            value=(
                f"**Produto:** `{product_name}`\n"
                f"**Opção:** `{campo_name or 'Padrão'}`\n"
                f"**Quantidade:** `{max(1, int(quantity or 1))}`\n"
                f"**Valor:** `R$ {float(value or 0):.2f}`\n"
                f"**Status:** `{status}`"
            ),
            inline=False,
        )
        await dm.send(embed=embed)
        return True
    except Exception:
        return False
