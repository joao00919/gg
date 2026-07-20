import disnake
from disnake import *

from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
import core

class edit_status:
    class edit_name_status_modal(disnake.ui.Modal):
        def __init__(self):
            database = db.get_document("custom_status")
            names = database.get("names", [database.get("name", "")])

            components = [
                disnake.ui.TextInput(
                    label="Nome do Status #1",
                    placeholder="Deixe em branco para não ter status",
                    custom_id="nome_status_1",
                    value=names[0] if names else "",
                    style=TextInputStyle.short,
                    required=False,
                    max_length=100,
                ),
            ]
            for i in range(2, 6):
                components.append(
                    disnake.ui.TextInput(
                        label=f"Nome do Status #{i}",
                        placeholder="Deixe em branco para não usar",
                        custom_id=f"nome_status_{i}",
                        value=names[i-1] if len(names) >= i else "",
                        style=TextInputStyle.short,
                        required=False,
                        max_length=100,
                    )
                )

            super().__init__(title="Editar Nomes do Status Rotativo", components=components)

        async def callback(self, inter: disnake.ModalInteraction):
            mode = db.get_document("custom_mode").get("mode")

            database = db.get_document("custom_status")
            
            status_names = []
            nome_status_1 = inter.text_values.get("nome_status_1")
            if nome_status_1:
                status_names.append(nome_status_1)
                for i in range(2, 6):
                    name = inter.text_values.get(f"nome_status_{i}")
                    if name:
                        status_names.append(name)
            
            database["names"] = status_names
            if "name" in database:
                del database["name"]

            db.save_document("custom_status", {}, database)
            
            await core.change_status(inter.bot)
            
            if mode == "embed":
                embed, components = edit_status.get_edit_status_panel_embed(inter)
                await inter.response.edit_message(content=None, embed=embed, components=components)
            else:
                await inter.response.edit_message(
                    components=edit_status.get_edit_status_panel_components(inter),
                )

    @staticmethod
    def get_edit_status_panel_components(inter: disnake.MessageInteraction) -> list[disnake.ui.Container]:
        status = db.get_document("custom_status")
        names = status.get("names", [status.get("name", "Nenhum")])
        names_display = " | ".join(names) if names and names != ["Nenhum"] else "Não configurado"

        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        statusname = {
            "online": "Online",
            "idle": "Ausente",
            "dnd": "Não Perturbar",
            "streaming": "Transmitindo",
            "offline": "Offline",
        }
        statusemoji = {
            "online": emoji.online,
            "idle": emoji.idle,
            "dnd": emoji.dnd,
            "streaming": emoji.streaming,
            "offline": emoji.off,
        }

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"""
# {emoji.z0}
-# Painel > Personalização > **Editar Status**
                """),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(f"""
**Informações salvas:**
-# Tipo: {statusemoji[status["type"]]} `{statusname[status["type"]]}`
-# Nomes: `{names_display}`
                """),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        placeholder="Selecione o status desejado",
                        custom_id="Personalizacao_EditarStatus_Tipo",
                        options=[
                            disnake.SelectOption(label="Online", value="online", emoji=emoji.online, default=status["type"] == "online"),
                            disnake.SelectOption(label="Ausente", value="idle", emoji=emoji.idle, default=status["type"] == "idle"),
                            disnake.SelectOption(label="Não Perturbar", value="dnd", emoji=emoji.dnd, default=status["type"] == "dnd"),
                            disnake.SelectOption(label="Transmitindo", value="streaming", emoji=emoji.streaming, default=status["type"] == "streaming"),
                        ],
                    ),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Editar nome do status", emoji=emoji.edit, custom_id="Personalizacao_EditarStatus_Nome"),
                ),
                **container_kwargs,
            ),
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Painel_Personalizacao"),
        ]
        
    @staticmethod
    def get_edit_status_panel_embed(inter: disnake.MessageInteraction):
        status = db.get_document("custom_status")
        names = status.get("names", [status.get("name", "Nenhum")])
        names_display = " | ".join(names) if names and names != ["Nenhum"] else "Não configurado"
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        statusname = {
            "online": "Online",
            "idle": "Ausente",
            "dnd": "Não Perturbar",
            "streaming": "Transmitindo",
            "offline": "Offline",
        }
        statusemoji = {
            "online": emoji.online,
            "idle": emoji.idle,
            "dnd": emoji.dnd,
            "streaming": emoji.streaming,
            "offline": emoji.off,
        }
        
        embed = disnake.Embed(
            title=f"Editar Status",
            description=f"**Informações salvas:**\n-# Tipo: {statusemoji[status['type']]} `{statusname[status['type']]}`\n-# Nomes: `{names_display}`",
            # timestamp=disnake.utils.utcnow()
        )
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            embed.color = primary_color

        # embed.set_footer(text=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else None)
        
        components = [
            disnake.ui.ActionRow(
                disnake.ui.StringSelect(
                    placeholder="Selecione o status desejado",
                    custom_id="Personalizacao_EditarStatus_Tipo",
                    options=[
                        disnake.SelectOption(label="Online", value="online", emoji=emoji.online, default=status["type"] == "online"),
                        disnake.SelectOption(label="Ausente", value="idle", emoji=emoji.idle, default=status["type"] == "idle"),
                        disnake.SelectOption(label="Não Perturbar", value="dnd", emoji=emoji.dnd, default=status["type"] == "dnd"),
                        disnake.SelectOption(label="Transmitindo", value="streaming", emoji=emoji.streaming, default=status["type"] == "streaming"),
                    ],
                ),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Editar nome do status", emoji=emoji.edit, custom_id="Personalizacao_EditarStatus_Nome"),
            ),
            disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Painel_Personalizacao"),
        ]
        return embed, components

    @staticmethod
    async def save_status(tipo: str, inter: disnake.MessageInteraction):
        status = db.get_document("custom_status")
        status["type"] = tipo
        db.save_document("custom_status", {}, status)
        await core.change_status(inter.bot)