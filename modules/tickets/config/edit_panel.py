import disnake
from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
from modules.tickets.purchase_link import TICKET_MODES, normalize_panel


def get_panels():
    config = db.get_document("tickets_config") or {}
    return config.get("panels", {})


class SelectPanelToEdit(disnake.ui.StringSelect):
    def __init__(self, panels_chunk: list[tuple[str, dict]], chunk_index: int, total_panels: int):
        options = [
            disnake.SelectOption(label=data["name"], value=panel_id, description=f"Clique para editar o painel")
            for panel_id, data in panels_chunk
        ]

        placeholder = "Selecione um painel para editar..."
        if total_panels > 25:
            start_index = chunk_index * 25 + 1
            end_index = start_index + len(panels_chunk) - 1
            placeholder = f"Selecione um painel... ({start_index}-{end_index})"

        if not options and total_panels == 0:
            options.append(disnake.SelectOption(label="Nenhum painel encontrado", value="disabled"))

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id=f"select_panel_to_edit_{chunk_index}",
            disabled=(total_panels == 0)
        )


def EditPanelView_components() -> list[disnake.ui.Container]:
    panels = get_panels()
    panel_items = list(panels.items())
    num_panels = len(panel_items)
    
    primary_color_hex = db.get_document("custom_colors").get("primary")
    
    container_components = [
        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Gerenciar Tickets > **Editar Painel**"),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small)
    ]

    if num_panels == 0:
        select = SelectPanelToEdit([], 0, 0)
        container_components.append(disnake.ui.ActionRow(select))
    else:
        chunk_size = 25
        for i in range(0, num_panels, chunk_size):
            chunk_index = i // chunk_size
            chunk = panel_items[i:i + chunk_size]
            select = SelectPanelToEdit(chunk, chunk_index, num_panels)
            container_components.append(disnake.ui.ActionRow(select))
            
    container_kwargs = {}
    if primary_color_hex:
        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

    container = disnake.ui.Container(*container_components, **container_kwargs)
    
    buttons = disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Painel_Ticket"),
        )
    
    return [container, buttons]

def EditPanelView_embed(inter: disnake.Interaction):
    panels = get_panels()
    panel_items = list(panels.items())
    num_panels = len(panel_items)

    primary_color_hex = db.get_document("custom_colors").get("primary")
    
    embed_kwargs = {}
    if primary_color_hex:
        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

    embed = disnake.Embed(
        title="Editar Painel",
        description="Selecione um painel abaixo para editar suas configurações.",
        **embed_kwargs
    )
    # embed.set_footer(text=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else None)
    # embed.timestamp = disnake.utils.utcnow()

    components = []
    if num_panels == 0:
        select = SelectPanelToEdit([], 0, 0)
        components.append(disnake.ui.ActionRow(select))
    else:
        chunk_size = 25
        for i in range(0, num_panels, chunk_size):
            chunk_index = i // chunk_size
            chunk = panel_items[i:i + chunk_size]
            select = SelectPanelToEdit(chunk, chunk_index, num_panels)
            components.append(disnake.ui.ActionRow(select))

    components.append(disnake.ui.ActionRow(
        disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Painel_Ticket"),
    ))

    return embed, components


def ChannelSelectView_components(panel_id: str) -> list[disnake.ui.Container]:
    primary_color_hex = db.get_document("custom_colors").get("primary")
    
    container_kwargs = {}
    if primary_color_hex:
        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

    container = disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Gerenciar Tickets > Editar Painel > **Editar Canal**"),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            disnake.ui.ActionRow(
                disnake.ui.ChannelSelect(
                    placeholder="Selecione um canal...",
                    custom_id=f"TicketEdit_SelectChannel_{panel_id}",
                    channel_types=[disnake.ChannelType.text],
                    min_values=1,
                    max_values=1,
                )
        ),
        **container_kwargs
    )
    
    buttons = disnake.ui.ActionRow(
        disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"TicketEdit_BackToPanel_{panel_id}")
    )
    
    return [container, buttons]

def ChannelSelectView_embed(inter: disnake.Interaction, panel_id: str):
    primary_color_hex = db.get_document("custom_colors").get("primary")

    embed_kwargs = {}
    if primary_color_hex:
        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

    embed = disnake.Embed(
        title="Editar Canal",
        description="Selecione o canal onde o painel de ticket será enviado.",
        **embed_kwargs
    )
    # embed.set_footer(text=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else None)
    # embed.timestamp = disnake.utils.utcnow()
    
    components = [
        disnake.ui.ActionRow(
            disnake.ui.ChannelSelect(
                placeholder="Selecione um canal...",
                custom_id=f"TicketEdit_SelectChannel_{panel_id}",
                channel_types=[disnake.ChannelType.text],
                min_values=1,
                max_values=1,
            )
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"TicketEdit_BackToPanel_{panel_id}")
        )
    ]

    return embed, components


def CategorySelectView_components(panel_id: str) -> list[disnake.ui.Container]:
    primary_color_hex = db.get_document("custom_colors").get("primary")
    
    container_kwargs = {}
    if primary_color_hex:
        container_kwargs["accent_colour"] = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

    container = disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Gerenciar Tickets > Editar Painel > **Editar Categoria**"),
            disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
            disnake.ui.ActionRow(
                disnake.ui.ChannelSelect(
                    placeholder="Selecione uma categoria...",
                    custom_id=f"TicketEdit_SelectCategory_{panel_id}",
                    channel_types=[disnake.ChannelType.category],
                    min_values=1,
                    max_values=1,
                )
        ),
        **container_kwargs
    )
    
    buttons = disnake.ui.ActionRow(
        disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"TicketEdit_BackToPanel_{panel_id}")
    )

    return [container, buttons]

def CategorySelectView_embed(inter: disnake.Interaction, panel_id: str):
    primary_color_hex = db.get_document("custom_colors").get("primary")

    embed_kwargs = {}
    if primary_color_hex:
        embed_kwargs["color"] = int(primary_color_hex.replace("#", ""), 16)

    embed = disnake.Embed(
        title=f"Editar Categoria",
        description="Selecione a categoria onde os tickets serão criados.",
        **embed_kwargs
    )
    # embed.set_footer(text=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else None)
    # embed.timestamp = disnake.utils.utcnow()
    
    components = [
        disnake.ui.ActionRow(
            disnake.ui.ChannelSelect(
                placeholder="Selecione uma categoria...",
                custom_id=f"TicketEdit_SelectCategory_{panel_id}",
                channel_types=[disnake.ChannelType.category],
                min_values=1,
                max_values=1,
            )
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id=f"TicketEdit_BackToPanel_{panel_id}")
        )
    ]

    return embed, components


def SpecificPanelView_components(inter: disnake.Interaction, panel_id: str) -> list[disnake.ui.Container]:
    panels = get_panels()
    panel_data = panels.get(panel_id)
    if not panel_data:
        return EditPanelView_components()
    normalize_panel(panel_data)

    colors = db.get_document("custom_colors") or {}
    container_kwargs = {}
    primary_color_hex = colors.get("primary")
    if primary_color_hex:
        try:
            container_kwargs["accent_colour"] = disnake.Colour(int(str(primary_color_hex).replace("#", ""), 16))
        except (TypeError, ValueError):
            pass

    panel_name = panel_data.get("name", "N/A")
    is_enabled = bool(panel_data.get("enabled", False))
    current_mode_key = str(panel_data.get("mode") or "channel")
    current_mode_label = "Canal" if current_mode_key == "channel" else "Tópico"
    channel_id = panel_data.get("channel_id")
    channel = inter.bot.get_channel(channel_id) if channel_id else None
    category_id = panel_data.get("category_id")
    category = inter.bot.get_channel(category_id) if category_id else None
    office_hours_data = panel_data.get("office_hours") or {}
    office_configured = bool(office_hours_data.get("start_time") and office_hours_data.get("end_time"))
    ai_enabled = bool(panel_data.get("ai_enabled", False))

    status_text = (
        "**Status e Configurações:**\n"
        f"{emoji.on if is_enabled else emoji.off} **Status:** `{'Ligado' if is_enabled else 'Desligado'}`\n"
        f"{emoji.route} **Modo de Atendimento:** `{current_mode_label}`\n"
        f"{emoji.clock} **Horário:** `{'Configurado' if office_configured else 'Não configurado'}`\n"
        f"{emoji.sparkles} **PromisseAI:** `{'Ativada' if ai_enabled else 'Desativada'}`"
    )

    message_id = panel_data.get("message_id")
    has_pending_changes = panel_data.get("has_pending_changes", True)
    publish_button_label = "Atualizar Painel" if message_id and has_pending_changes else "Enviar Painel"

    management_buttons = [
        disnake.ui.Button(
            label="",
            style=disnake.ButtonStyle.grey,
            emoji=emoji.power,
            custom_id=f"TicketEdit_ToggleEnable_{panel_id}",
        )
    ]
    if current_mode_key == "channel":
        management_buttons.append(
            disnake.ui.Button(
                label="Definir Categoria",
                style=disnake.ButtonStyle.blurple,
                emoji=emoji.folder,
                custom_id=f"TicketEdit_SetCategory_{panel_id}",
                disabled=not is_enabled,
            )
        )
    management_buttons.extend([
        disnake.ui.Button(
            label="Editar Canais",
            style=disnake.ButtonStyle.blurple,
            emoji=emoji.textc,
            custom_id=f"TicketEdit_SetChannel_{panel_id}",
            disabled=not is_enabled,
        ),
        disnake.ui.Button(
            label="Editar Cargos",
            style=disnake.ButtonStyle.blurple,
            emoji=emoji.role,
            custom_id=f"TicketEdit_ConfigRoles_{panel_id}",
            disabled=not is_enabled,
        ),
    ])

    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Gerenciar Tickets > Editar Painel > **{panel_name}**"),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.TextDisplay(status_text),
        disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Editar Opções", style=disnake.ButtonStyle.grey, emoji=emoji.embed, custom_id=f"TicketEdit_EditOptions_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label="Editar Mensagens", style=disnake.ButtonStyle.grey, emoji=emoji.message, custom_id=f"TicketEdit_OpenMessageEditor_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label=f"Modo: {current_mode_label}", style=disnake.ButtonStyle.grey, emoji=emoji.route, custom_id=f"TicketEdit_CycleMode_{panel_id}", disabled=not is_enabled),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Horário de Atendimento", style=disnake.ButtonStyle.grey, emoji=emoji.clock, custom_id=f"TicketEdit_Hours_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label="PromisseAI", style=disnake.ButtonStyle.grey, emoji=emoji.sparkles, custom_id=f"TicketEdit_ConfigIA_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label="Preferências", style=disnake.ButtonStyle.grey, emoji=emoji.settings2, custom_id=f"TicketEdit_Preferences_{panel_id}", disabled=not is_enabled),
        ),
        disnake.ui.ActionRow(*management_buttons),
        disnake.ui.ActionRow(
            disnake.ui.Button(label=publish_button_label, style=disnake.ButtonStyle.green, emoji=emoji.arrow, custom_id=f"TicketEdit_Sync_{panel_id}"),
            disnake.ui.Button(label="Deletar Painel", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"TicketEdit_Delete_{panel_id}"),
            disnake.ui.Button(label="Deletar Tickets", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"TicketEdit_DeleteTickets_{panel_id}"),
        ),
        **container_kwargs,
    )
    return [
        container,
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Ticket_EditarPainel")
        ),
    ]


def SpecificPanelView_embed(inter: disnake.Interaction, panel_id: str):
    panels = get_panels()
    panel_data = panels.get(panel_id)
    if not panel_data:
        return EditPanelView_embed(inter)
    normalize_panel(panel_data)

    colors = db.get_document("custom_colors") or {}
    embed_kwargs = {}
    primary_color_hex = colors.get("primary")
    if primary_color_hex:
        try:
            embed_kwargs["color"] = int(str(primary_color_hex).replace("#", ""), 16)
        except (TypeError, ValueError):
            pass

    panel_name = panel_data.get("name", "N/A")
    is_enabled = bool(panel_data.get("enabled", False))
    current_mode_key = str(panel_data.get("mode") or "channel")
    current_mode_label = "Canal" if current_mode_key == "channel" else "Tópico"
    office_hours_data = panel_data.get("office_hours") or {}
    office_configured = bool(office_hours_data.get("start_time") and office_hours_data.get("end_time"))
    ai_enabled = bool(panel_data.get("ai_enabled", False))
    status_text = (
        f"{emoji.on if is_enabled else emoji.off} **Status:** `{'Ligado' if is_enabled else 'Desligado'}`\n"
        f"{emoji.route} **Modo de Atendimento:** `{current_mode_label}`\n"
        f"{emoji.clock} **Horário:** `{'Configurado' if office_configured else 'Não configurado'}`\n"
        f"{emoji.sparkles} **PromisseAI:** `{'Ativada' if ai_enabled else 'Desativada'}`"
    )
    embed = disnake.Embed(title=f"Editando Painel: {panel_name}", description=status_text, **embed_kwargs)

    message_id = panel_data.get("message_id")
    has_pending_changes = panel_data.get("has_pending_changes", True)
    publish_button_label = "Atualizar Painel" if message_id and has_pending_changes else "Enviar Painel"
    management_buttons = [
        disnake.ui.Button(label="", style=disnake.ButtonStyle.grey, emoji=emoji.power, custom_id=f"TicketEdit_ToggleEnable_{panel_id}")
    ]
    if current_mode_key == "channel":
        management_buttons.append(disnake.ui.Button(label="Definir Categoria", style=disnake.ButtonStyle.blurple, emoji=emoji.folder, custom_id=f"TicketEdit_SetCategory_{panel_id}", disabled=not is_enabled))
    management_buttons.extend([
        disnake.ui.Button(label="Editar Canais", style=disnake.ButtonStyle.blurple, emoji=emoji.textc, custom_id=f"TicketEdit_SetChannel_{panel_id}", disabled=not is_enabled),
        disnake.ui.Button(label="Editar Cargos", style=disnake.ButtonStyle.blurple, emoji=emoji.role, custom_id=f"TicketEdit_ConfigRoles_{panel_id}", disabled=not is_enabled),
    ])
    components = [
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Editar Opções", emoji=emoji.embed, custom_id=f"TicketEdit_EditOptions_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label="Editar Mensagens", emoji=emoji.message, custom_id=f"TicketEdit_OpenMessageEditor_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label=f"Modo: {current_mode_label}", emoji=emoji.route, custom_id=f"TicketEdit_CycleMode_{panel_id}", disabled=not is_enabled),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Horário de Atendimento", emoji=emoji.clock, custom_id=f"TicketEdit_Hours_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label="PromisseAI", emoji=emoji.sparkles, custom_id=f"TicketEdit_ConfigIA_{panel_id}", disabled=not is_enabled),
            disnake.ui.Button(label="Preferências", emoji=emoji.settings2, custom_id=f"TicketEdit_Preferences_{panel_id}", disabled=not is_enabled),
        ),
        disnake.ui.ActionRow(*management_buttons),
        disnake.ui.ActionRow(
            disnake.ui.Button(label=publish_button_label, style=disnake.ButtonStyle.green, emoji=emoji.arrow, custom_id=f"TicketEdit_Sync_{panel_id}"),
            disnake.ui.Button(label="Deletar Painel", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"TicketEdit_Delete_{panel_id}"),
            disnake.ui.Button(label="Deletar Tickets", style=disnake.ButtonStyle.red, emoji=emoji.delete, custom_id=f"TicketEdit_DeleteTickets_{panel_id}"),
        ),
        disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id="Ticket_EditarPainel")),
    ]
    return embed, components

