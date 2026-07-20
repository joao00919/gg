from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import disnake
from disnake.ext import commands

from functions.audit_log import write_audit_log
from functions.database import database as db
from functions.emoji import emoji
from functions.perms import perms
from functions.utils import utils
from functions.interaction_runtime import respond_error, respond_panel
from functions.loja_products import ensure_product_description
from modules.loja.cart.purchase_manager import PurchaseManager
from modules.loja.products.cog import GerenciarProdutos
from modules.loja.products.product.configurar import ConfigurarProduto
from modules.loja.products.product.create import CreateProductModal, build_product_payload
from modules.loja.products.product.campos.fields.configurar import ConfigurarCampo
from modules.loja.products.product.coupons.configurar import ConfigurarCupom
from modules.loja.products.product.coupons.create import CreateCouponModal
from modules.loja.personalization.qr_customization import QRCodeGenerator
from modules.loja.product_panels import (
    build_admin_payload,
    build_publish_style_payload,
    create_panel as create_product_panel,
    get_panels as get_product_panels,
    panel_autocomplete_values,
    publish_panel as publish_product_panel,
    resolve_panel,
)

GUILD_IDS = [utils.obter_server_principal()]
logger = logging.getLogger("zynex.commands")


def _product_name(product: dict) -> str:
    return str(product.get("name") or "Produto")


def _stock_count(product: dict) -> int:
    total = 0
    for field in (product.get("campos") or {}).values():
        stock = field.get("stock", field.get("estoque", []))
        if isinstance(stock, (list, dict)):
            total += len(stock)
        elif isinstance(stock, int):
            total += max(0, stock)
    return total


class ZYNEXCommands(commands.Cog):
    """Comandos de compatibilidade exigidos pela interface ZYNEX Systems."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _admin(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if await perms.check(inter):
            return True
        text = f"{emoji.wrong} Você não tem permissão para usar este comando."
        if not inter.response.is_done():
            await inter.response.send_message(text, ephemeral=True)
        else:
            await inter.followup.send(text, ephemeral=True)
        return False

    async def product_autocomplete(self, inter: disnake.ApplicationCommandInteraction, text: str):
        products = db.get_document("loja_products") or {}
        query = (text or "").lower()
        values = []
        for product_id, product in products.items():
            label = f"{_product_name(product)} — {product_id}"
            if not query or query in label.lower():
                values.append(label[:100])
        return values[:25]

    async def panel_autocomplete(self, inter: disnake.ApplicationCommandInteraction, text: str):
        return panel_autocomplete_values(text)

    async def coupon_autocomplete(self, inter: disnake.ApplicationCommandInteraction, text: str):
        products = db.get_document("loja_products") or {}
        query = (text or "").lower()
        values = []
        for product_id, product in products.items():
            for coupon_id, coupon in (product.get("cupons") or {}).items():
                label = f"{coupon.get('name') or coupon_id} — {product_id}:{coupon_id}"
                if not query or query in label.lower():
                    values.append(label[:100])
        return values[:25]

    @staticmethod
    def _resolve_product(value: Optional[str]) -> str:
        return str(value or "").rsplit(" — ", 1)[-1].strip()

    @staticmethod
    def _resolve_coupon(value: str) -> tuple[str, str]:
        raw = str(value or "").rsplit(" — ", 1)[-1].strip()
        if ":" not in raw:
            return "", ""
        product_id, coupon_id = raw.split(":", 1)
        return product_id, coupon_id

    async def _send_panel(self, inter: disnake.ApplicationCommandInteraction, panel: dict, *, ephemeral: bool = True):
        """Envia painéis com validação de emojis e sem deixar a interação expirar."""
        return await respond_panel(inter, panel, ephemeral=ephemeral)

    async def _publish_product(
        self,
        inter: disnake.ApplicationCommandInteraction,
        product_id: str,
        channel: disnake.TextChannel,
    ):
        """Publica um produto já cadastrado sem criar ou duplicar o cadastro."""
        products = db.get_document("loja_products") or {}
        product = products.get(product_id)

        if not product:
            await inter.followup.send(
                f"{emoji.wrong} Produto não encontrado.", ephemeral=True
            )
            return None

        if not product.get("active", True):
            await inter.followup.send(
                f"{emoji.wrong} Este produto está desativado. Ative-o antes de publicar.",
                ephemeral=True,
            )
            return None

        if channel is None or not hasattr(channel, "send"):
            await inter.followup.send(
                f"{emoji.wrong} Selecione um canal de texto válido.", ephemeral=True
            )
            return None

        mode = (db.get_document("custom_mode") or {}).get("mode", "components")
        try:
            if mode == "embed":
                embed = ConfigurarProduto._build_legacy_embed(product, inter.guild)
                buy_config = (product.get("info") or {}).get("buy_button") or {}
                button = disnake.ui.Button(
                    label=buy_config.get("label", "Comprar"),
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.cart,
                    custom_id=f"buy_product:{product_id}",
                )
                msg = await channel.send(
                    embed=embed,
                    components=[disnake.ui.ActionRow(button)],
                )
                published_mode = "legacy"
            else:
                components = ConfigurarProduto._build_container_components(
                    product,
                    image_inside=False,
                    product_id=product_id,
                )
                msg = await channel.send(
                    components=components,
                    flags=disnake.MessageFlags(is_components_v2=True),
                )
                published_mode = "container_outside"
        except disnake.Forbidden:
            await inter.followup.send(
                f"{emoji.wrong} Não tenho permissão para enviar mensagens nesse canal.",
                ephemeral=True,
            )
            return None
        except disnake.HTTPException as exc:
            await inter.followup.send(
                f"{emoji.wrong} O Discord recusou a publicação do produto: {str(exc)[:200]}",
                ephemeral=True,
            )
            return None

        now = datetime.now(timezone.utc)
        product.setdefault("messages", []).append(
            {
                "message_id": msg.id,
                "channel_id": channel.id,
                "guild_id": inter.guild.id,
                "mode": published_mode,
                "created_at": int(now.timestamp()),
            }
        )
        product.setdefault("audit", []).append(
            {
                "action": "product_published",
                "admin_id": str(inter.author.id),
                "timestamp": now.isoformat(),
            }
        )
        product["updated_at"] = now.isoformat()
        products[product_id] = product
        db.save_document("loja_products", products)

        await inter.followup.send(
            f"{emoji.correct} Produto publicado em {channel.mention}. "
            f"[Ir para o produto]({msg.jump_url})",
            ephemeral=True,
        )
        return msg

    @commands.slash_command(name="cleardm", description="🛠️ | Utilidades | Limpe todas as mensagens do bot na sua DM!", guild_ids=GUILD_IDS)
    async def cleardm(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)
        deleted = 0
        failed = 0
        try:
            dm = inter.author.dm_channel or await inter.author.create_dm()
            async for msg in dm.history(limit=100):
                if self.bot.user and msg.author.id == self.bot.user.id:
                    try:
                        await msg.delete()
                        deleted += 1
                        await asyncio.sleep(0.25)
                    except Exception:
                        failed += 1
            suffix = f". Falhas: **{failed}**" if failed else ""
            await inter.followup.send(f"{emoji.correct} Mensagens do bot removidas: **{deleted}**{suffix}", ephemeral=True)
        except Exception as exc:
            write_audit_log("cleardm_failed", user_id=getattr(inter.author, "id", None), error=exc)
            await inter.followup.send(f"{emoji.wrong} Não foi possível limpar a DM.", ephemeral=True)

    @commands.slash_command(name="config", description="💰 | Vendas Moderação | Configure um produto", guild_ids=GUILD_IDS)
    async def config(self, inter: disnake.ApplicationCommandInteraction, produto: Optional[str] = commands.Param(default=None, autocomplete=product_autocomplete)):
        if not await self._admin(inter):
            return
        product_id = self._resolve_product(produto)
        products = db.get_document("loja_products") or {}
        if product_id:
            if product_id not in products:
                await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
                return
            await self._send_panel(inter, ConfigurarProduto.panel(inter, product_id))
            return
        await self._send_panel(inter, GerenciarProdutos(self.bot).panel(inter))

    @commands.slash_command(name="config_painel", description="💰 | Vendas Moderação | Configure um painel", guild_ids=GUILD_IDS)
    async def config_painel(
        self,
        inter: disnake.ApplicationCommandInteraction,
        painel: str = commands.Param(autocomplete=panel_autocomplete),
    ):
        if not await self._admin(inter):
            return
        panel_id = resolve_panel(painel)
        if panel_id not in get_product_panels():
            return await inter.response.send_message(
                f"{emoji.wrong} Painel não encontrado.", ephemeral=True
            )
        await self._send_panel(inter, build_admin_payload(panel_id))

    @commands.slash_command(name="configcupom", description="🛠️💰 | Vendas Moderação | Configure um cupom", guild_ids=GUILD_IDS)
    async def configcupom(self, inter: disnake.ApplicationCommandInteraction, cupom: str = commands.Param(autocomplete=coupon_autocomplete)):
        if not await self._admin(inter):
            return
        product_id, coupon_id = self._resolve_coupon(cupom)
        products = db.get_document("loja_products") or {}
        if not product_id or coupon_id not in (products.get(product_id, {}).get("cupons") or {}):
            await inter.response.send_message(f"{emoji.wrong} Cupom não encontrado.", ephemeral=True)
            return
        await self._send_panel(inter, ConfigurarCupom.panel(inter, product_id, coupon_id))

    @commands.slash_command(name="criados", description="💰 | Vendas Moderação | Veja os itens cadastrados no bot", guild_ids=GUILD_IDS)
    async def criados(self, inter: disnake.ApplicationCommandInteraction):
        if not await self._admin(inter):
            return
        products = db.get_document("loja_products") or {}
        if not products:
            await inter.response.send_message("Nenhum produto cadastrado.", ephemeral=True)
            return
        lines = []
        coupon_count = 0
        for product_id, product in sorted(products.items(), key=lambda item: _product_name(item[1]).lower()):
            coupons = product.get("cupons") or {}
            coupon_count += len(coupons)
            status = "ativo" if product.get("active", True) else "inativo"
            lines.append(f"• **{_product_name(product)}** · `{product_id}` · estoque **{_stock_count(product)}** · {status} · {len(coupons)} cupom(ns)")
        description = "\n".join(lines[:40])
        if len(lines) > 40:
            description += f"\n… e mais {len(lines) - 40} produto(s)."
        embed = disnake.Embed(title="Cadzynexs ZYNEX", description=description, color=disnake.Color.blurple(), timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Produtos: {len(products)} · Cupons: {coupon_count}")
        await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="criar",
        description="💰 | Vendas Moderação | Cadastra um novo produto no bot",
        guild_ids=GUILD_IDS,
    )
    async def criar(
        self,
        inter: disnake.ApplicationCommandInteraction,
        nome: str = commands.Param(
            description="Coloque o NOME do produto!",
            min_length=1,
            max_length=100,
        ),
        descricao: Optional[str] = commands.Param(
            default=None,
            description="Descrição que aparecerá na publicação do produto",
            max_length=1000,
        ),
    ):
        """Cria o produto imediatamente, igual ao fluxo visual da referência."""
        if not await self._admin(inter):
            return

        product_name = str(nome or "").strip()
        if not product_name:
            await inter.response.send_message(
                f"{emoji.wrong} Coloque o nome do produto.", ephemeral=True
            )
            return

        product_description = str(descricao or "").strip() or f"{product_name} disponível para compra."
        product_id = utils.gerar_id()
        field_id = utils.gerar_id()
        now_ts = int(disnake.utils.utcnow().timestamp())

        product = build_product_payload(
            product_id=product_id,
            name=product_name,
            description=product_description,
            banner=None,
            hex_color="#ADD8E6",
            delivery_type="automatic",
        )
        product["promisse_style"] = True
        product["active"] = True
        product["info"]["thumbnail"] = None
        product["info"]["required_role_id"] = None
        product["info"]["coupons_enabled"] = True
        product["info"]["category_name"] = None
        product["campos"][field_id] = {
            "id": field_id,
            "name": product_name,
            "price": 0.0,
            "emoji": None,
            "pre_description": product_description,
            "description": product_description,
            "instructions": None,
            "category_id": None,
            "created_at": now_ts,
            "updated_at": now_ts,
            "advanced": {},
            "stock": [],
            "stock_style": "traditional",
            "cargos": {
                "adicionar": [],
                "remover": [],
                "authorized": [],
            },
            "condicoes": {
                "valorMin": None,
                "valorMax": None,
                "quantidadeMin": None,
                "quantidadeMax": None,
            },
        }

        products = db.get_document("loja_products") or {}
        products[product_id] = product
        db.save_document("loja_products", products)

        try:
            panel = ConfigurarCampo.panel(inter, product_id, field_id)
            await self._send_panel(inter, panel, ephemeral=True)
            await inter.followup.send(
                f"{emoji.correct} O produto **{product_name}** foi criado com sucesso!",
                ephemeral=True,
            )
        except Exception:
            logger.exception("Produto salvo, mas o painel /criar não pôde ser exibido")
            await respond_error(
                inter,
                f"O produto **{product_name}** foi salvo, mas o painel não pôde ser exibido.",
            )

    @commands.slash_command(
        name="set",
        description="💰 | Vendas Moderação | Publique um produto já criado",
        guild_ids=GUILD_IDS,
    )
    async def set_product(
        self,
        inter: disnake.ApplicationCommandInteraction,
        produto: str = commands.Param(
            description="Produto que será publicado",
            autocomplete=product_autocomplete,
        ),
        canal: Optional[disnake.TextChannel] = commands.Param(
            default=None,
            description="Canal onde o produto será publicado",
        ),
    ):
        """Abre a escolha de estilo para publicar um produto existente."""
        if not await self._admin(inter):
            return

        product_id = self._resolve_product(produto)
        products = db.get_document("loja_products") or {}
        product = products.get(product_id)
        if not product:
            return await inter.response.send_message(
                f"{emoji.wrong} Produto não encontrado.", ephemeral=True
            )
        if not product.get("active", True):
            return await inter.response.send_message(
                f"{emoji.wrong} Este produto está desativado. Ative-o antes de publicar.",
                ephemeral=True,
            )

        ensure_product_description(product)
        products[product_id] = product
        db.save_document("loja_products", products)

        target = canal or inter.channel
        if target is None or not hasattr(target, "send"):
            return await inter.response.send_message(
                f"{emoji.wrong} Selecione um canal de texto válido.", ephemeral=True
            )

        publisher = self.bot.get_cog("SendProduct")
        if publisher is None or not hasattr(publisher, "_build_mode_selector"):
            return await inter.response.send_message(
                f"{emoji.wrong} O módulo de publicação não está disponível.", ephemeral=True
            )

        selector = publisher._build_mode_selector(product_id, str(target.id))
        await inter.response.send_message(
            components=[selector],
            ephemeral=True,
            flags=disnake.MessageFlags(is_components_v2=True),
        )

    @commands.slash_command(
        name="criar_painel",
        description="💰 | Vendas Moderação | Crie um painel select menu para seus produtos",
        guild_ids=GUILD_IDS,
    )
    async def criar_painel(
        self,
        inter: disnake.ApplicationCommandInteraction,
        nome: str = commands.Param(default="Painel de Produtos", max_length=100),
        descricao: Optional[str] = commands.Param(
            default=None,
            description="Descrição exibida acima do select menu",
            max_length=1000,
        ),
    ):
        if not await self._admin(inter):
            return
        panel_id, panel = create_product_panel(nome, inter.author.id)
        if str(descricao or "").strip():
            panels = get_product_panels()
            panel["description"] = str(descricao).strip()[:1000]
            panels[panel_id] = panel
            from modules.loja.product_panels import save_panels
            save_panels(panels)
        await self._send_panel(inter, build_admin_payload(panel_id))

    @commands.slash_command(
        name="set_painel",
        description="💰 | Vendas Moderação | Publique um painel já criado",
        guild_ids=GUILD_IDS,
    )
    async def set_painel(
        self,
        inter: disnake.ApplicationCommandInteraction,
        painel: str = commands.Param(autocomplete=panel_autocomplete),
        canal: Optional[disnake.TextChannel] = commands.Param(
            default=None,
            description="Canal onde o painel será publicado",
        ),
    ):
        if not await self._admin(inter):
            return
        panel_id = resolve_panel(painel)
        panel = get_product_panels().get(panel_id)
        if not panel:
            return await inter.response.send_message(
                f"{emoji.wrong} Painel não encontrado.", ephemeral=True
            )
        target = canal or inter.channel
        if target is None or not hasattr(target, "send"):
            return await inter.response.send_message(
                f"{emoji.wrong} Selecione um canal de texto válido.", ephemeral=True
            )
        try:
            payload = build_publish_style_payload(panel_id, int(target.id))
            await self._send_panel(inter, payload)
        except Exception as exc:
            await respond_error(inter, f"Não foi possível abrir os estilos do painel: {str(exc)[:200]}")

    @commands.slash_command(name="criarcupom", description="💰 | Vendas Moderação | Crie um cupom de desconto", guild_ids=GUILD_IDS)
    async def criarcupom(self, inter: disnake.ApplicationCommandInteraction, produto: str = commands.Param(autocomplete=product_autocomplete)):
        if not await self._admin(inter):
            return
        product_id = self._resolve_product(produto)
        if product_id not in (db.get_document("loja_products") or {}):
            await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
            return
        await inter.response.send_modal(CreateCouponModal(product_id))

    @commands.slash_command(name="dm", description="🛠️ | Moderação | Envie uma mensagem no privado de um usuário", guild_ids=GUILD_IDS)
    async def dm(self, inter: disnake.ApplicationCommandInteraction, usuario: disnake.Member, mensagem: str):
        if not await self._admin(inter):
            return
        try:
            await usuario.send(mensagem, allowed_mentions=disnake.AllowedMentions.none())
            await inter.response.send_message(f"{emoji.correct} Mensagem enviada para {usuario.mention}.", ephemeral=True)
        except disnake.Forbidden:
            await inter.response.send_message(f"{emoji.wrong} O usuário está com a DM fechada.", ephemeral=True)

    @commands.slash_command(name="estatisticas", description="📊 | Vendas Moderação | Veja as estatísticas de vendas do bot", guild_ids=GUILD_IDS)
    async def estatisticas(self, inter: disnake.ApplicationCommandInteraction):
        if not await self._admin(inter):
            return
        stats = PurchaseManager.get_statistics()
        products_sold = stats.get("products_sold") or {}
        top = max(products_sold.values(), key=lambda value: value.get("count", 0), default={})
        carts = (db.get_document("loja_data") or {}).get("carts") or {}
        pending = sum(1 for cart in carts.values() if str(cart.get("status", "")).lower() in {"pending", "pendente"})
        expired = sum(1 for cart in carts.values() if str(cart.get("status", "")).lower() in {"expired", "expirado"})
        abandoned = sum(1 for cart in carts.values() if str(cart.get("status", "")).lower() in {"cancelled", "canceled", "abandoned", "cancelado"})
        revenue = float(stats.get("total_revenue", 0) or 0)
        embed = disnake.Embed(title="📊 Estatísticas", color=disnake.Color.blurple(), timestamp=datetime.now(timezone.utc))
        embed.description = (
            f"**Total vendido:** R$ {revenue:,.2f}\n"
            f"**Quantidade de vendas:** {stats.get('total_purchases', 0)}\n"
            f"**Produtos vendidos:** {stats.get('total_items_sold', 0)}\n"
            f"**Clientes únicos:** {stats.get('unique_customers', 0)}\n"
            f"**Produto mais vendido:** {top.get('name', 'Nenhum')}\n"
            f"**Carrinhos abandonados:** {abandoned}\n"
            f"**Pagamentos pendentes:** {pending}\n"
            f"**Pagamentos expirados:** {expired}\n"
            f"**Ticket médio:** R$ {float(stats.get('average_ticket', 0) or 0):,.2f}"
        ).replace(",", "X").replace(".", ",").replace("X", ".")
        embed.set_footer(text="Métricas calculadas pelo histórico interno; a API de pagamento não foi alterada.")
        await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(name="qrcode_personalizar", description="💰 | Vendas Moderação | Personalize seu QR Code de pagamentos", guild_ids=GUILD_IDS)
    async def qrcode_personalizar(self, inter: disnake.ApplicationCommandInteraction):
        try:
            if not await self._admin(inter):
                return
            await self._send_panel(inter, QRCodeGenerator.panel(inter))
        except Exception:
            logger.exception("Falha ao abrir /qrcode_personalizar")
            await respond_error(
                inter,
                "Não foi possível abrir a personalização do QR Code. O erro foi registrado no console.",
            )

    @commands.slash_command(name="rankprodutos", description="🏆 | Vendas | Veja os produtos que mais geraram lucro", guild_ids=GUILD_IDS)
    async def rankprodutos(self, inter: disnake.ApplicationCommandInteraction):
        if not await self._admin(inter):
            return
        products = list((PurchaseManager.get_statistics().get("products_sold") or {}).values())
        products.sort(key=lambda item: float(item.get("revenue") or 0), reverse=True)
        if not products:
            await inter.response.send_message("Ainda não há vendas registradas.", ephemeral=True)
            return
        lines = [f"**{index}. {item.get('name', 'Produto')}** — R$ {float(item.get('revenue') or 0):,.2f} · {item.get('count', 0)} venda(s)" for index, item in enumerate(products[:15], 1)]
        await inter.response.send_message(embed=disnake.Embed(title="Ranking de produtos", description="\n".join(lines), color=disnake.Color.gold()), ephemeral=True)

    @commands.slash_command(name="resetar", description="🛠️💰 | Vendas Moderação | Resete vendas, ranking e cupons", guild_ids=GUILD_IDS)
    async def resetar(self, inter: disnake.ApplicationCommandInteraction, confirmacao: str = commands.Param(description="Digite CONFIRMAR")):
        if not await self._admin(inter):
            return
        if confirmacao.strip().upper() != "CONFIRMAR":
            await inter.response.send_message(f"{emoji.warn} Operação cancelada. Digite `CONFIRMAR` para executar.", ephemeral=True)
            return
        db.save_document("loja_buys", {"purchases": {}})
        products = db.get_document("loja_products") or {}
        for product in products.values():
            info = product.setdefault("info", {})
            info["purchasesIds"] = []
            for coupon in (product.get("cupons") or {}).values():
                coupon["uses_count"] = 0
                coupon["used_by"] = []
        db.save_document("loja_products", products)
        write_audit_log("sales_metrics_reset", admin_id=inter.author.id, guild_id=inter.guild_id, details={"scope": "sales_rank_coupons"})
        await inter.response.send_message(f"{emoji.correct} Vendas, ranking e contadores de cupons foram redefinidos. Produtos, estoque e pagamentos foram preservados.", ephemeral=True)

    @commands.slash_command(name="stockid", description="📦 | Vendas Moderação | Veja o estoque de um produto", guild_ids=GUILD_IDS)
    async def stockid(self, inter: disnake.ApplicationCommandInteraction, produto: str = commands.Param(autocomplete=product_autocomplete)):
        if not await self._admin(inter):
            return
        product_id = self._resolve_product(produto)
        product = (db.get_document("loja_products") or {}).get(product_id)
        if not product:
            await inter.response.send_message(f"{emoji.wrong} Produto não encontrado.", ephemeral=True)
            return
        lines = []
        for field_id, field in (product.get("campos") or {}).items():
            stock = field.get("stock", field.get("estoque", []))
            count = len(stock) if isinstance(stock, (list, dict)) else int(stock or 0)
            lines.append(f"• **{field.get('name', field_id)}** · `{field_id}` · estoque **{count}**")
        await inter.response.send_message(embed=disnake.Embed(title=f"Estoque — {_product_name(product)}", description="\n".join(lines) if lines else "Nenhuma opção cadastrada.", color=disnake.Color.blurple()), ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(ZYNEXCommands(bot))
