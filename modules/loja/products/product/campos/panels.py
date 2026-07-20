import disnake
from functions.database import database as db
from functions.emoji import emoji
from functions.utils import utils
from functions.text_utils import safe_textdisplay, safe_select_option_label, safe_select_option_description
from functions.loja_products import container_kwargs_for_product, embed_kwargs_for_product, get_stock_quantity
from modules.loja.cart.stock_manager import StockManager

def _get_stock_display(product_id: str, field_id: str) -> str:
    """Retorna a quantidade de estoque formatada (Infinito ou número)"""
    products = db.get_document("loja_products") or {}
    product = products.get(product_id, {})
    campo = product.get("campos", {}).get(field_id, {})
    
    # Verificar se é estoque infinito
    if campo.get("infinite_stock", {}).get("enabled"):
        return "Infinito"
    
    # Obter estoque do sistema centralizado
    stock_qtd = StockManager.get_available_stock(product_id, field_id)
    return str(stock_qtd)


def _dropdown_categorias(product: dict, product_id: str) -> disnake.ui.Select:
    categorias = product.get("categorias", {}) or {}
    options = []
    disabled = False
    for categoria in categorias.values():
        name = categoria.get("name") or categoria.get("id")
        label = safe_select_option_label(name)
        description = safe_select_option_description(f"Opções: {len(categoria.get('campos', {}))}")
        options.append(disnake.SelectOption(label=label, value=categoria.get("id"), description=description))
    if not options:
        disabled = True
        options.append(disnake.SelectOption(label="Nenhuma categoria encontrada", value="disabled"))
    return disnake.ui.StringSelect(
        placeholder=f"[{len(categorias)}] Selecione uma categoria",
        options=options,
        custom_id=f"Loja_Categorias_Select:{product_id}",
        disabled=disabled,
    )


def _dropdown_campos(product: dict, product_id: str) -> disnake.ui.Select:
    campos = product.get("campos", {}) or {}
    options = []
    disabled = False
    for campo in campos.values():
        name = campo.get("name") or campo.get("id")
        label = safe_select_option_label(name)
        price = utils.format_price_brl(campo.get('price'))
        stock_qtd = _get_stock_display(product_id=product_id, field_id=campo.get("id"))
        description = safe_select_option_description(f"Preço: {price} | Estoque: {stock_qtd}")
        options.append(disnake.SelectOption(label=label, value=campo.get("id"), description=description))
    if not options:
        disabled = True
        options.append(disnake.SelectOption(label="Nenhuma opção encontrada", value="disabled"))
    return disnake.ui.StringSelect(
        placeholder=f"[{len(campos)}] Selecione uma opção do produto",
        options=options,
        custom_id=f"Loja_Campos_Select:{product_id}",
        disabled=disabled,
    )


def build_components(product: dict, product_id: str) -> dict:
    dropdown_campos = _dropdown_campos(product, product_id)
    container_kwargs = container_kwargs_for_product(product)

    product_name = safe_textdisplay(product.get('name', product_id), 50)
    header_text = safe_textdisplay(f"# {emoji.z0}\n-# Painel > Loja > {product_name} > **Opções do Produto**")
    
    return {"components": [
        disnake.ui.Container(
            disnake.ui.TextDisplay(header_text),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay("Selecione uma opção do produto para gerenciar.\nPara criar, use o botão abaixo."),
            disnake.ui.Separator(),
            disnake.ui.ActionRow(dropdown_campos),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Criar Opção", style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id=f"Loja_CriarCampo:{product_id}"),
            ),
            **container_kwargs
        ),
        disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"Loja_ConfigurarProduto:{product_id}")),
    ]}


def build_embed(product: dict, product_id: str) -> dict:
    dropdown_campos = _dropdown_campos(product, product_id)
    embed_kwargs = embed_kwargs_for_product(product)

    embed = disnake.Embed(
        description=f"-# Painel > Loja > {product.get('name', product_id)} > **Opções do Produto**\n\nSelecione uma opção do produto para gerenciar.",
        **embed_kwargs
    )

    components = [
        disnake.ui.ActionRow(dropdown_campos),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Criar Opção", style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id=f"Loja_CriarCampo:{product_id}"),
        ),
        disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"Loja_ConfigurarProduto:{product_id}")),
    ]
    return {"embed": embed, "components": components}


def build_category_fields_components(product: dict, product_id: str, category_id: str) -> dict:
    campos = product.get("campos", {}) or {}
    options = []
    disabled = False
    for campo in campos.values():
        if campo.get("category_id") != category_id:
            continue
        name = campo.get("name") or campo.get("id")
        label = safe_select_option_label(name)
        price = utils.format_price_brl(campo.get('price'))
        stock_qtd = _get_stock_display(product_id=product_id, field_id=campo.get("id"))
        description = safe_select_option_description(f"Preço: {price} | Estoque: {stock_qtd}")
        options.append(disnake.SelectOption(label=label, value=campo.get("id"), description=description))
    if not options:
        disabled = True
        options.append(disnake.SelectOption(label="Nenhuma opção nesta categoria", value="disabled"))

    dropdown_campos_categoria = disnake.ui.StringSelect(
        placeholder=f"Selecione uma opção do produto desta categoria",
        options=options,
        custom_id=f"Loja_CamposCategoria_Select:{product_id}:{category_id}",
        disabled=disabled,
    )

    container_kwargs = container_kwargs_for_product(product)
    product_name = safe_textdisplay(product.get('name', product_id), 50)
    header_text = safe_textdisplay(f"# {emoji.z0}\n-# Painel > Loja > {product_name} > **Opções da Categoria**")
    
    return {"components": [
        disnake.ui.Container(
            disnake.ui.TextDisplay(header_text),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay("Selecione uma opção do produto para gerenciar ou crie uma nova."),
            disnake.ui.Separator(),
            disnake.ui.ActionRow(dropdown_campos_categoria),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Criar Opção", style=disnake.ButtonStyle.green, emoji=emoji.plus, custom_id=f"Loja_CriarCampoCategoria:{product_id}:{category_id}"),
            ),
            **container_kwargs
        ),
        disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"Loja_ConfigurarCategoria:{product_id}:{category_id}")),
    ]}


def build_category_fields_embed(product: dict, product_id: str, category_id: str) -> dict:
    embed_kwargs = embed_kwargs_for_product(product)
    embed = disnake.Embed(
        description=f"-# Painel > Loja > {product.get('name', product_id)} > **Opções da Categoria**",
        **embed_kwargs
    )
    # Dropdown built in components to avoid duplication here
    components = build_category_fields_components(product, product_id, category_id)["components"]
    return {"embed": embed, "components": components}


