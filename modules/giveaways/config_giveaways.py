import disnake
from functions.utils import utils
from functions.database import database as db
from functions.message import message, embed_message
from functions.emoji import emoji

def SelectModeView_components():
    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Sorteios > **Criar Sorteio**"),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.TextDisplay("Selecione o modo do sorteio que deseja criar."),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Modo Real", style=disnake.ButtonStyle.green, emoji=emoji.gift, custom_id="GiveawayCreate_SetMode_real"),
            disnake.ui.Button(label="Modo Fake", style=disnake.ButtonStyle.danger, emoji=emoji.gift2, custom_id="GiveawayCreate_SetMode_falso"),
        ),
    )
    buttons = disnake.ui.ActionRow(
        disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Giveaways_Painel")
    )
    return [container, buttons]

def SelectModeView_embed():
    embed = disnake.Embed(
        title="Criar Sorteio",
        description="Selecione o modo do sorteio que deseja criar."
    )
    components = [
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Modo Real", style=disnake.ButtonStyle.green, emoji=emoji.gift, custom_id="GiveawayCreate_SetMode_real"),
            disnake.ui.Button(label="Modo Fake", style=disnake.ButtonStyle.danger, emoji=emoji.gift2, custom_id="GiveawayCreate_SetMode_falso"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Giveaways_Painel")
        )
    ]
    return embed, components

class CreateGiveawayModal(disnake.ui.Modal):
    def __init__(self, inter: disnake.CommandInteraction, mode: str):
        self.inter = inter
        self.mode = mode
        components = [
            disnake.ui.TextInput(
                label="Nome do Sorteio",
                placeholder="Ex: Sorteio de Nitro",
                custom_id="giveaway_name",
                max_length=50,
            ),
        ]
        super().__init__(title="Criar Novo Sorteio", components=components, custom_id="create_giveaway_modal")

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter, send=False)
        else:
            await message.wait(inter, send=False)
        
        giveaway_id = utils.gerar_id()
        giveaway_name = inter.text_values["giveaway_name"]

        config = db.obter("database/giveaways/giveaways_data.json")
        if not config:
            config = {}
            
        config[giveaway_id] = {
            "name": giveaway_name,
            "mode": self.mode,
            "author_id": inter.author.id,
            "created_at": int(disnake.utils.utcnow().timestamp())
        }
        db.salvar("database/giveaways/giveaways_data.json", config)
        
        mode = db.get_document("custom_mode").get("mode")

        if mode == "components":
            components = SpecificGiveawayView_components(inter, giveaway_id)
            await inter.edit_original_message(components=components)
        else:
            embed, components = SpecificGiveawayView_embed(inter, giveaway_id)
            await inter.edit_original_message(content=None, embed=embed, components=components)

class RenameGiveawayModal(disnake.ui.Modal):
    """Altera o nome do sorteio diretamente pelo painel de edição."""

    def __init__(self, original_inter: disnake.Interaction, giveaway_id: str, current_name: str):
        self.original_inter = original_inter
        self.giveaway_id = giveaway_id
        components = [
            disnake.ui.TextInput(
                label="Nome do Sorteio",
                placeholder="Digite o novo nome do sorteio",
                custom_id="giveaway_name",
                value=current_name[:50],
                min_length=1,
                max_length=50,
                required=True,
            )
        ]
        super().__init__(
            title="Alterar Nome do Sorteio",
            components=components,
            custom_id=f"rename_giveaway_modal_{giveaway_id}",
        )

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter, send=False)
        else:
            await message.wait(inter, send=False)

        config = db.obter("database/giveaways/giveaways_data.json") or {}
        giveaway = config.get(self.giveaway_id)
        if not giveaway:
            await inter.followup.send("Sorteio não encontrado.", ephemeral=True)
            return

        giveaway["name"] = inter.text_values["giveaway_name"].strip()
        db.salvar("database/giveaways/giveaways_data.json", config)

        if mode == "components":
            await self.original_inter.edit_original_message(
                components=SpecificGiveawayView_components(inter, self.giveaway_id)
            )
        else:
            embed, components = SpecificGiveawayView_embed(inter, self.giveaway_id)
            await self.original_inter.edit_original_message(
                content=None, embed=embed, components=components
            )


def get_giveaways():
    return db.obter("database/giveaways/giveaways_data.json") or {}

class SelectGiveawayToEdit(disnake.ui.StringSelect):
    def __init__(self, giveaways_chunk: list[tuple[str, dict]], chunk_index: int, total_giveaways: int):
        options = [
            disnake.SelectOption(label=data["name"], value=giveaway_id, description=f"Clique para editar o sorteio")
            for giveaway_id, data in giveaways_chunk
        ]

        placeholder = "Selecione um sorteio para editar..."
        if total_giveaways > 25:
            start_index = chunk_index * 25 + 1
            end_index = start_index + len(giveaways_chunk) - 1
            placeholder = f"Selecione um sorteio... ({start_index}-{end_index})"

        if not options and total_giveaways == 0:
            options.append(disnake.SelectOption(label="Nenhum sorteio encontrado", value="disabled"))

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id=f"select_giveaway_to_edit_{chunk_index}",
            disabled=(total_giveaways == 0)
        )

def EditGiveawayView_components() -> list[disnake.ui.Container]:
    giveaways = get_giveaways()
    giveaway_items = list(giveaways.items())
    num_giveaways = len(giveaway_items)
    
    primary_color_hex = db.get_document("custom_colors").get("primary")
    
    container_components = [
        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Sorteios > **Editar Sorteio**"),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small)
    ]

    if num_giveaways == 0:
        select = SelectGiveawayToEdit([], 0, 0)
        container_components.append(disnake.ui.ActionRow(select))
    else:
        chunk_size = 25
        for i in range(0, num_giveaways, chunk_size):
            chunk_index = i // chunk_size
            chunk = giveaway_items[i:i + chunk_size]
            select = SelectGiveawayToEdit(chunk, chunk_index, num_giveaways)
            container_components.append(disnake.ui.ActionRow(select))
            
    container_kwargs = {}
    if primary_color_hex:
        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

    container = disnake.ui.Container(*container_components, **container_kwargs)
    
    buttons = disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Giveaways_Painel"),
        )
    
    return [container, buttons]

def EditGiveawayView_embed(inter: disnake.Interaction):
    giveaways = get_giveaways()
    giveaway_items = list(giveaways.items())
    num_giveaways = len(giveaway_items)

    primary_color_hex = db.get_document("custom_colors").get("primary")
    
    embed_kwargs = {}
    if primary_color_hex:
        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

    embed = disnake.Embed(
        title="Editar Sorteio",
        description="Selecione um sorteio abaixo para editar suas configurações.",
        **embed_kwargs
    )

    components = []
    if num_giveaways == 0:
        select = SelectGiveawayToEdit([], 0, 0)
        components.append(disnake.ui.ActionRow(select))
    else:
        chunk_size = 25
        for i in range(0, num_giveaways, chunk_size):
            chunk_index = i // chunk_size
            chunk = giveaway_items[i:i + chunk_size]
            select = SelectGiveawayToEdit(chunk, chunk_index, num_giveaways)
            components.append(disnake.ui.ActionRow(select))

    components.append(disnake.ui.ActionRow(
        disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Giveaways_Painel"),
    ))

    return embed, components

def _giveaway_reference_status(giveaway_id: str, giveaway_data: dict) -> tuple[str, str, str]:
    giveaway_mode = giveaway_data.get("mode", "real")
    mode_text = "Real" if giveaway_mode == "real" else "Fake"
    monitor_text = "Ativo" if giveaway_data.get("monitor_enabled", False) else "Inativo"
    prize = giveaway_data.get("prize", {}) or {}
    prize_type = prize.get("type", "none")
    prize_text = {
        "none": "Nenhum",
        "content": prize.get("content") or "Conteúdo na DM",
    }.get(prize_type, str(prize_type).replace("_", " ").title())
    return mode_text, monitor_text, prize_text


def SpecificGiveawayView_components(inter: disnake.Interaction, giveaway_id: str) -> list[disnake.ui.Container]:
    giveaways = get_giveaways()
    giveaway_data = giveaways.get(giveaway_id)
    if not giveaway_data:
        return EditGiveawayView_components()

    primary_color_hex = db.get_document("custom_colors").get("primary")
    container_kwargs = {}
    if primary_color_hex:
        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

    giveaway_name = giveaway_data.get("name", "Novo Sorteio")
    mode_text, monitor_text, prize_text = _giveaway_reference_status(giveaway_id, giveaway_data)
    status_text = (
        "## Configurações do Sorteio\n"
        f"**ID:** `{giveaway_id}`\n"
        f"**Modo:** `{mode_text}`\n"
        f"**Monitor:** `{monitor_text}`\n"
        f"**Prêmio:** `{prize_text}`"
    )

    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Sorteios > Editar > **{giveaway_name}**"),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.TextDisplay(status_text),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Alterar Nome", style=disnake.ButtonStyle.grey, emoji=emoji.edit, custom_id=f"GiveawayEdit_Rename_{giveaway_id}"),
            disnake.ui.Button(label="Configurar Prêmio", style=disnake.ButtonStyle.grey, emoji=emoji.gift, custom_id=f"GiveawayEdit_Prize_{giveaway_id}"),
            disnake.ui.Button(label="Requisitos", style=disnake.ButtonStyle.grey, emoji=emoji.star, custom_id=f"GiveawayEdit_Requirements_{giveaway_id}"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Cargos Bônus", style=disnake.ButtonStyle.grey, emoji=emoji.role, custom_id=f"GiveawayEdit_BonusRoles_{giveaway_id}"),
            disnake.ui.Button(label="Customizar Mensagem", style=disnake.ButtonStyle.grey, emoji=emoji.message, custom_id=f"GiveawayEdit_SetMessage_{giveaway_id}"),
            disnake.ui.Button(label="Configurar Envio", style=disnake.ButtonStyle.blurple, emoji=emoji.truck, custom_id=f"GiveawayEdit_ConfigSend_{giveaway_id}"),
        ),
        **container_kwargs,
    )

    buttons = disnake.ui.ActionRow(
        disnake.ui.Button(label="Excluir Sorteio", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"GiveawayEdit_Delete_{giveaway_id}"),
        disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Giveaways_VerSorteios"),
    )
    return [container, buttons]


def SpecificGiveawayView_embed(inter: disnake.Interaction, giveaway_id: str):
    giveaways = get_giveaways()
    giveaway_data = giveaways.get(giveaway_id)
    if not giveaway_data:
        return EditGiveawayView_embed(inter)

    primary_color_hex = db.get_document("custom_colors").get("primary")
    embed_kwargs = {}
    if primary_color_hex:
        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

    giveaway_name = giveaway_data.get("name", "Novo Sorteio")
    mode_text, monitor_text, prize_text = _giveaway_reference_status(giveaway_id, giveaway_data)
    embed = disnake.Embed(
        title=f"Editando Sorteio: {giveaway_name}",
        description=(
            "### Configurações do Sorteio\n"
            f"**ID:** `{giveaway_id}`\n"
            f"**Modo:** `{mode_text}`\n"
            f"**Monitor:** `{monitor_text}`\n"
            f"**Prêmio:** `{prize_text}`"
        ),
        **embed_kwargs,
    )
    components = [
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Alterar Nome", style=disnake.ButtonStyle.grey, emoji=emoji.edit, custom_id=f"GiveawayEdit_Rename_{giveaway_id}"),
            disnake.ui.Button(label="Configurar Prêmio", style=disnake.ButtonStyle.grey, emoji=emoji.gift, custom_id=f"GiveawayEdit_Prize_{giveaway_id}"),
            disnake.ui.Button(label="Requisitos", style=disnake.ButtonStyle.grey, emoji=emoji.star, custom_id=f"GiveawayEdit_Requirements_{giveaway_id}"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Cargos Bônus", style=disnake.ButtonStyle.grey, emoji=emoji.role, custom_id=f"GiveawayEdit_BonusRoles_{giveaway_id}"),
            disnake.ui.Button(label="Customizar Mensagem", style=disnake.ButtonStyle.grey, emoji=emoji.message, custom_id=f"GiveawayEdit_SetMessage_{giveaway_id}"),
            disnake.ui.Button(label="Configurar Envio", style=disnake.ButtonStyle.blurple, emoji=emoji.truck, custom_id=f"GiveawayEdit_ConfigSend_{giveaway_id}"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Excluir Sorteio", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"GiveawayEdit_Delete_{giveaway_id}"),
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Giveaways_VerSorteios"),
        ),
    ]
    return embed, components


def LogChannelSelectView_components(giveaway_id: str) -> list[disnake.ui.Container]:
    primary_color_hex = db.get_document("custom_colors").get("primary")
    
    container_kwargs = {}
    if primary_color_hex:
        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

    container = disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Sorteios > Editar > **Definir Canal de Logs**"),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            disnake.ui.ActionRow(
                disnake.ui.ChannelSelect(
                    placeholder="Selecione um canal...",
                    custom_id=f"GiveawayEdit_SelectLogChannel_{giveaway_id}",
                    channel_types=[disnake.ChannelType.text],
                    min_values=1,
                    max_values=1,
                )
        ),
        **container_kwargs
    )
    
    buttons = disnake.ui.ActionRow(
        disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"GiveawayEdit_BackToPanel_{giveaway_id}")
    )
    
    return [container, buttons]

def LogChannelSelectView_embed(inter: disnake.Interaction, giveaway_id: str):
    primary_color_hex = db.get_document("custom_colors").get("primary")

    embed_kwargs = {}
    if primary_color_hex:
        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

    embed = disnake.Embed(
        title="Definir Canal de Logs",
        description="Selecione o canal onde os logs do sorteio serão enviados.",
        **embed_kwargs
    )
    
    components = [
        disnake.ui.ActionRow(
            disnake.ui.ChannelSelect(
                placeholder="Selecione um canal...",
                custom_id=f"GiveawayEdit_SelectLogChannel_{giveaway_id}",
                channel_types=[disnake.ChannelType.text],
                min_values=1,
                max_values=1,
            )
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"GiveawayEdit_BackToPanel_{giveaway_id}")
        )
    ]

    return embed, components
