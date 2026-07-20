import disnake

from disnake.ext import commands
from functions.database import database as db
from functions.message import message, embed_message

from .modals import CreateFieldModal, EditFieldModal, EditInstructionsModal
from .configurar import ConfigurarCampo
from ..cog import GerenciarCamposCategorias


class FieldActions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id or ""
        if custom_id.startswith("Loja_CriarCampo:"):
            product_id = custom_id.split(":", 1)[1]
            modal = CreateFieldModal(product_id)
            await inter.response.send_modal(modal)
            return

        if custom_id.startswith("Loja_CriarCampoCategoria:"):
            _, rest = custom_id.split(":", 1)
            product_id, category_id = rest.split(":", 1)
            modal = CreateFieldModal(product_id, category_id=category_id)
            await inter.response.send_modal(modal)
            return

        if custom_id.startswith("Loja_EditarCampo:"):
            _, rest = custom_id.split(":", 1)
            product_id, field_id = rest.split(":", 1)
            modal = EditFieldModal(product_id, field_id)
            await inter.response.send_modal(modal)
            return

        if custom_id.startswith("Loja_ApagarCampo:"):
            _, rest = custom_id.split(":", 1)
            product_id, field_id = rest.split(":", 1)
            await message.wait(inter, send=False)

            products = db.get_document("loja_products")
            product = products.get(product_id) or {}
            campos = product.get("campos") or {}
            if field_id in campos:
                campos.pop(field_id, None)
                product["campos"] = campos
                products[product_id] = product
                db.save_document("loja_products", products)
                
                # Sincronizar silenciosamente todas as mensagens do produto
                from modules.loja.products.product.edit import sync_product_messages_silently
                await sync_product_messages_silently(inter.client, product_id)

            mode = db.get_document("custom_mode").get("mode")
            panel_data = GerenciarCamposCategorias(inter.bot).panel(inter, product_id)
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                await inter.edit_original_message(content=None, **panel_data)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(**panel_data)

        if custom_id.startswith("Loja_EstoqueCampo:"):
            _, rest = custom_id.split(":", 1)
            product_id, field_id = rest.split(":", 1)
            from .estoque.visualizar import panel as stock_panel
            mode = db.get_document("custom_mode").get("mode")
            panel_data = stock_panel(inter, product_id, field_id)
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                await inter.edit_original_message(content=None, **panel_data)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(**panel_data)
            return

        if custom_id.startswith("Loja_CargosCampo:"):
            _, rest = custom_id.split(":", 1)
            product_id, field_id = rest.split(":", 1)
            from .cargos.configurar import ConfigurarCargosCampo
            mode = db.get_document("custom_mode").get("mode")
            panel_data = ConfigurarCargosCampo.panel(inter, product_id, field_id)
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                await inter.edit_original_message(content=None, **panel_data)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(**panel_data)
            return

        if custom_id.startswith("Loja_CondicoesCampo:"):
            _, rest = custom_id.split(":", 1)
            product_id, field_id = rest.split(":", 1)
            from .condicoes.modals import CondicoesModal
            await inter.response.send_modal(CondicoesModal(product_id, field_id))
            return

        if custom_id.startswith("Loja_InstrucoesCampo:"):
            _, rest = custom_id.split(":", 1)
            product_id, field_id = rest.split(":", 1)
            modal = EditInstructionsModal(product_id, field_id)
            await inter.response.send_modal(modal)
            return


def setup(bot: commands.Bot):
    bot.add_cog(FieldActions(bot))


