import disnake
from disnake.ext import commands
from functions.emoji import emoji
from functions.database import database as db
from functions.message import message, embed_message
from functions.permission_matrix import get_config as get_matrix_config, matrix_markdown


class GerenciarPermissoes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def get_perms_users():
        """Retorna a lista de IDs de usuários com permissão"""
        config = db.obter("config.json")
        return config.get("bot", {}).get("perms", [])

    @staticmethod
    def save_perms_users(perms_list: list):
        """Salva a lista de permissões no config.json"""
        config = db.obter("config.json")
        config["bot"]["perms"] = perms_list
        db.salvar("config.json", config)

    @staticmethod
    def panel(inter: disnake.MessageInteraction, bot: commands.Bot = None):
        """Retorna o painel de gerenciamento de permissões"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        
        # Obter lista de usuários com permissão
        perms_users = GerenciarPermissoes.get_perms_users()
        
        # Formatar lista de usuários
        if perms_users:
            users_text = ""
            for user_id in perms_users:
                users_text += f"{emoji.members} <@{user_id}>\n"
        else:
            users_text = f"{emoji.wrong} Nenhum usuário com acesso."
        
        components = [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Configurações > **Gerenciar Permissões**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(
                    f"**Gerencie as Permissões**\n\n"
                    f"**Usuários com Acesso:**\n{users_text}"
                ),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.Button(
                        label="Adicionar",
                        style=disnake.ButtonStyle.green,
                        emoji=emoji.plus,
                        custom_id="Permissoes_Adicionar"
                    ),
                    disnake.ui.Button(
                        label="Remover",
                        style=disnake.ButtonStyle.danger,
                        emoji=emoji.minus,
                        custom_id="Permissoes_Remover"
                    ),
                    disnake.ui.Button(
                        label="Matriz Visual",
                        style=disnake.ButtonStyle.secondary,
                        emoji=emoji.members,
                        custom_id="Permissoes_Matriz"
                    ),
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Painel_Configuracoes"
                )
            )
        ]
        
        return {"components": components}

    @staticmethod
    def panel_embed(inter: disnake.MessageInteraction, bot: commands.Bot = None):
        """Retorna o painel em formato embed"""
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        
        # Obter lista de usuários com permissão
        perms_users = GerenciarPermissoes.get_perms_users()
        
        # Formatar lista de usuários
        if perms_users:
            users_text = ""
            for user_id in perms_users:
                users_text += f"{emoji.members} <@{user_id}>\n"
        else:
            users_text = f"{emoji.wrong} Nenhum usuário com acesso."
        
        embed = disnake.Embed(
            title="Gerenciar Permissões",
            description=(
                f"-# Painel > Configurações > **Gerenciar Permissões**\n\n"
                f"**Usuários com Acesso:**\n{users_text}"
            )
        )
        
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            embed.color = primary_color
        
        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Adicionar",
                    style=disnake.ButtonStyle.green,
                    emoji=emoji.plus,
                    custom_id="Permissoes_Adicionar"
                ),
                disnake.ui.Button(
                    label="Remover",
                    style=disnake.ButtonStyle.danger,
                    emoji=emoji.minus,
                    custom_id="Permissoes_Remover"
                ),
                disnake.ui.Button(
                    label="Matriz Visual",
                    style=disnake.ButtonStyle.secondary,
                    emoji=emoji.members,
                    custom_id="Permissoes_Matriz"
                ),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(
                    label="Voltar",
                    style=disnake.ButtonStyle.grey,
                    emoji=emoji.back,
                    custom_id="Painel_Configuracoes"
                )
            )
        ]
        
        return embed, components

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Permissoes_Adicionar":
            # Modal para adicionar usuário
            await inter.response.send_modal(
                title="Adicionar Usuário",
                custom_id="Permissoes_Adicionar_Modal",
                components=[
                    disnake.ui.TextInput(
                        label="ID do Usuário",
                        placeholder="Ex: 123456789012345678",
                        custom_id="user_id",
                        style=disnake.TextInputStyle.short,
                        max_length=20,
                        required=True
                    )
                ]
            )
        
        elif inter.component.custom_id == "Permissoes_Remover":
            # Verificar se há usuários para remover
            perms_users = self.get_perms_users()
            
            if not perms_users:
                await inter.response.send_message(
                    f"{emoji.wrong} Não há usuários com permissão para remover.",
                    ephemeral=True
                )
                return
            
            # Modal para remover usuário
            await inter.response.send_modal(
                title="Remover Usuário",
                custom_id="Permissoes_Remover_Modal",
                components=[
                    disnake.ui.TextInput(
                        label="ID do Usuário",
                        placeholder="Ex: 123456789012345678",
                        custom_id="user_id",
                        style=disnake.TextInputStyle.short,
                        max_length=20,
                        required=True
                    )
                ]
            )
        
        elif inter.component.custom_id == "Permissoes_Matriz":
            cfg = get_matrix_config()
            roles = cfg.get("role_ids", {})
            admin_role = f"<@&{roles['admin']}>" if roles.get("admin") else "`Não definido`"
            finance_role = f"<@&{roles['finance']}>" if roles.get("finance") else "`Não definido`"
            support_role = f"<@&{roles['support']}>" if roles.get("support") else "`Não definido`"
            role_text = (
                "**Cargos vinculados**\n"
                f"Admin: {admin_role}\n"
                f"Financeiro: {finance_role}\n"
                f"Suporte: {support_role}"
            )
            text = f"**Matriz de permissões**\n```\n{matrix_markdown()}\n```\n{role_text}\n\n-# Configure os cargos em Configurações > Cargos. A validação é aplicada pelo backend."
            mode = (db.get_document("custom_mode") or {}).get("mode", "components")
            if mode == "embed":
                embed = disnake.Embed(title="Matriz visual de permissões", description=text)
                await inter.response.edit_message(embed=embed, components=[
                    disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id="Permissoes_Voltar"))
                ])
            else:
                colors = db.get_document("custom_colors") or {}
                kwargs = {}
                if colors.get("primary"):
                    kwargs["accent_colour"] = disnake.Colour(int(colors["primary"].replace("#", ""), 16))
                await inter.response.edit_message(components=[
                    disnake.ui.Container(disnake.ui.TextDisplay(text), **kwargs),
                    disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", emoji=emoji.back, custom_id="Permissoes_Voltar"))
                ])

        elif inter.component.custom_id == "Permissoes_Voltar":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = self.panel_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                panel = self.panel(inter, self.bot)
                await inter.edit_original_message(**panel, flags=disnake.MessageFlags(is_components_v2=True))

    @commands.Cog.listener("on_modal_submit")
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id == "Permissoes_Adicionar_Modal":
            user_id = inter.text_values["user_id"].strip()
            
            # Validar ID
            if not user_id.isdigit():
                await inter.response.send_message(
                    f"{emoji.wrong} ID inválido! O ID deve conter apenas números.",
                    ephemeral=True
                )
                return
            
            # Verificar se usuário já tem permissão
            perms_users = self.get_perms_users()
            if user_id in perms_users:
                await inter.response.send_message(
                    f"{emoji.wrong} Este usuário já possui permissão!",
                    ephemeral=True
                )
                return
            
            # Adicionar usuário
            perms_users.append(user_id)
            self.save_perms_users(perms_users)
            
            await inter.response.send_message(
                f"{emoji.correct} Usuário <@{user_id}> adicionado com sucesso!",
                ephemeral=True
            )
            
            # Atualizar painel
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                embed, components = self.panel_embed(inter)
                await inter.message.edit(content=None, embed=embed, components=components)
            else:
                panel = self.panel(inter, self.bot)
                await inter.message.edit(**panel, flags=disnake.MessageFlags(is_components_v2=True))
        
        elif inter.custom_id == "Permissoes_Remover_Modal":
            user_id = inter.text_values["user_id"].strip()
            
            # Validar ID
            if not user_id.isdigit():
                await inter.response.send_message(
                    f"{emoji.wrong} ID inválido! O ID deve conter apenas números.",
                    ephemeral=True
                )
                return
            
            # Verificar se usuário tem permissão
            perms_users = self.get_perms_users()
            if user_id not in perms_users:
                await inter.response.send_message(
                    f"{emoji.wrong} Este usuário não possui permissão!",
                    ephemeral=True
                )
                return
            
            # Verificar se é o owner
            config = db.obter("config.json")
            owner_id = config.get("bot", {}).get("owner", "")
            if user_id == owner_id:
                await inter.response.send_message(
                    f"{emoji.wrong} Você não pode remover a permissão do dono do bot!",
                    ephemeral=True
                )
                return
            
            # Remover usuário
            perms_users.remove(user_id)
            self.save_perms_users(perms_users)
            
            await inter.response.send_message(
                f"{emoji.correct} Usuário <@{user_id}> removido com sucesso!",
                ephemeral=True
            )
            
            # Atualizar painel
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                embed, components = self.panel_embed(inter)
                await inter.message.edit(content=None, embed=embed, components=components)
            else:
                panel = self.panel(inter, self.bot)
                await inter.message.edit(**panel, flags=disnake.MessageFlags(is_components_v2=True))


def setup(bot: commands.Bot):
    bot.add_cog(GerenciarPermissoes(bot))
