import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
from .edit_info import edit_info_bot_modal
from .edit_status import edit_status
from .edit_colors import EditColorsCog, EditColorsModal
from .edit_mode import EditMode

class Personalizacao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def personalizacao_components(self, inter: disnake.MessageInteraction) -> list[disnake.ui.Container]:
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")

        container_kwargs = {}
        primary_hex = primary_color_hex or "#5c5ef0"
        try:
            primary_color = int(primary_hex.replace("#", ""), 16)
        except Exception:
            primary_color = int("5c5ef0", 16)
        container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > **Personalização**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    "Configure e personalize o status, informações, cores e o modo de exibição do bot.\n"
                    "Selecione uma seção abaixo para configurar."
                ),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="Personalizacao_Select",
                        placeholder="Selecione uma seção para configurar",
                        options=[
                            disnake.SelectOption(label="Editar Status", value="editar_status", description="Atualize tipo e nomes do status", emoji=emoji.edit),
                            disnake.SelectOption(label="Editar Informações", value="editar_info", description="Atualize nome, avatar e informações do bot", emoji=emoji.coupon),
                            disnake.SelectOption(label="Modo de Exibição", value="modo_exibicao", description="Alterne entre embed e components", emoji=emoji.embed),
                            disnake.SelectOption(label="Editar Cores", value="editar_cores", description="Personalize as cores do bot", emoji=emoji.wand),
                        ],
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey,
                                  emoji=emoji.back, custom_id="PainelInicial"),
            )
        ]
        
    def personalizacao_embed(self, inter: disnake.MessageInteraction):
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        embed = disnake.Embed(
            title=f"Personalização",
            description="Configure e personalize o status, informações, cores e o modo de exibição do bot.\nSelecione uma seção abaixo para configurar.",
            # timestamp=disnake.utils.utcnow()
        )
        primary_hex = primary_color_hex or "#5c5ef0"
        try:
            primary_color = int(primary_hex.replace("#", ""), 16)
        except Exception:
            primary_color = int("5c5ef0", 16)
        embed.color = primary_color
        
        # embed.set_footer(text=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else None)
        components = [
            disnake.ui.ActionRow(
                disnake.ui.StringSelect(
                    custom_id="Personalizacao_Select",
                    placeholder="Selecione uma seção para configurar",
                    options=[
                        disnake.SelectOption(label="Editar Status", value="editar_status", description="Atualize tipo e nomes do status", emoji=emoji.edit),
                        disnake.SelectOption(label="Editar Informações", value="editar_info", description="Atualize nome, avatar e informações do bot", emoji=emoji.coupon),
                        disnake.SelectOption(label="Modo de Exibição", value="modo_exibicao", description="Alterne entre embed e components", emoji=emoji.embed),
                        disnake.SelectOption(label="Editar Cores", value="editar_cores", description="Personalize as cores do bot", emoji=emoji.wand),
                    ],
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey,
                                    emoji=emoji.back, custom_id="PainelInicial"),
            )
        ]
        return embed, components

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        mode = db.get_document("custom_mode").get("mode")

        if inter.component.custom_id == "Painel_Personalizacao":
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = self.personalizacao_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(components=self.personalizacao_components(inter))

        elif inter.component.custom_id == "Personalizacao_EditarCores":
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = EditColorsCog.get_panel_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(components=EditColorsCog.get_panel_components(inter))

        elif inter.component.custom_id == "Personalizacao_EditarCores_Modal":
            await inter.response.send_modal(EditColorsModal())

        elif inter.component.custom_id == "Personalizacao_VisualizarCores":
            await inter.response.defer(ephemeral=True)
            if mode == "embed":
                embeds, components = EditColorsCog.get_preview_embed(inter)
                await inter.edit_original_response(embeds=embeds, components=components)
            else:
                components = EditColorsCog.get_preview_components(inter)
                await inter.edit_original_response(components=components)

        elif inter.component.custom_id == "Personalizacao_VisualizarCores_Voltar":
            await inter.response.defer()
            if mode == "embed":
                embed, components = EditColorsCog.get_panel_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                components = EditColorsCog.get_panel_components(inter)
                await inter.edit_original_message(components=components)

        elif inter.component.custom_id == "Personalizacao_ModoExibicao":
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = EditMode.mode_change_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(components=EditMode.mode_change_components(inter))

        elif inter.component.custom_id == "Personalizacao_EditarInfo":
            default_name = (inter.bot.user.name if getattr(inter.bot, 'user', None) and inter.bot.user else None)
            await inter.response.send_modal(edit_info_bot_modal(default_name=default_name))

        elif inter.component.custom_id == "Personalizacao_EditarStatus":
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = edit_status.get_edit_status_panel_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(
                    components=edit_status.get_edit_status_panel_components(inter)
                )

        elif inter.component.custom_id == "Personalizacao_EditarStatus_Nome":
            await inter.response.send_modal(edit_status.edit_name_status_modal())

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if inter.component.custom_id == "Personalizacao_Select":
            choice = inter.values[0]
            if choice == "editar_info":
                default_name = (inter.bot.user.name if getattr(inter.bot, 'user', None) and inter.bot.user else None)
                await inter.response.send_modal(edit_info_bot_modal(default_name=default_name))
                return
            elif choice == "editar_cores":
                if mode == "embed":
                    await embed_message.wait(inter, send=False)
                    embed, components = EditColorsCog.get_panel_embed(inter)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                else:
                    await message.wait(inter, send=False)
                    await inter.edit_original_message(components=EditColorsCog.get_panel_components(inter))
                return
            elif choice == "modo_exibicao":
                if mode == "embed":
                    await embed_message.wait(inter, send=False)
                    embed, components = EditMode.mode_change_embed(inter)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                else:
                    await message.wait(inter, send=False)
                    await inter.edit_original_message(components=EditMode.mode_change_components(inter))
                return
            elif choice == "editar_status":
                if mode == "embed":
                    await embed_message.wait(inter, send=False)
                    embed, components = edit_status.get_edit_status_panel_embed(inter)
                    await inter.edit_original_message(content=None, embed=embed, components=components)
                else:
                    await message.wait(inter, send=False)
                    await inter.edit_original_message(
                        components=edit_status.get_edit_status_panel_components(inter)
                    )
                return
        if inter.component.custom_id == "Personalizacao_EditarStatus_Tipo":
            await edit_status.save_status(inter.values[0], inter)
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = edit_status.get_edit_status_panel_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(
                    components=edit_status.get_edit_status_panel_components(inter)
                )

        elif inter.component.custom_id == "Personalizacao_EditarModoExibicao":
            await inter.response.defer()

            new_mode = inter.values[0]
            db.save_document("custom_mode", {}, {"mode": new_mode})
            
            await inter.delete_original_message()

            if new_mode == "embed":
                embed, components = EditMode.mode_change_embed(inter)
                await inter.followup.send(embed=embed, components=components, ephemeral=True)
            else:
                components = EditMode.mode_change_components(inter)
                await inter.followup.send(components=components, ephemeral=True, flags=disnake.MessageFlags(is_components_v2=True))
