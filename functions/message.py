"""
Mensagens pré-definidas para o bot.
"""

import disnake
from functions.emoji import emoji

class message:
    @staticmethod
    async def wait(inter: disnake.MessageInteraction, send=False, ephemeral=True, followup=False) -> disnake.Message:
        components = disnake.ui.TextDisplay(f"{emoji.loading} Carregando informações...")

        if send:
            return await inter.response.send_message(
                components=components,
                flags=disnake.MessageFlags(is_components_v2=True),
                ephemeral=ephemeral
            )
        elif followup:
            return await inter.followup.send(
                components=components,
                flags=disnake.MessageFlags(is_components_v2=True),
                ephemeral=ephemeral
            )
        else:
            if not inter.response.is_done():
                await inter.response.defer(with_message=False)
                
            return await inter.edit_original_message(
                embed=None,
                components=components
            )

    @staticmethod
    async def missing_perms(inter: disnake.MessageInteraction) -> disnake.Message:
        components = [
            disnake.ui.Container(
                disnake.ui.TextDisplay("🔒 Você não tem permissão para usar este comando.")
            )
        ]
        return await inter.response.send_message(
            components=components,
            ephemeral=True	,
            flags=disnake.MessageFlags(is_components_v2=True)
        )

    @staticmethod
    async def error(inter: disnake.MessageInteraction, message: str, send=False, followup=False, component=None) -> disnake.Message:
        components = [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"❌ {message}"),
            )
        ]
        if component:
            if isinstance(component, (list, tuple)):
                components.extend(component)
            else:
                components.append(component)

        if send:
            return await inter.response.send_message(
                components=components,
                ephemeral=True,
                flags=disnake.MessageFlags(is_components_v2=True)
            )
        elif followup:
            return await inter.followup.send(
                components=components,
                ephemeral=True,
                flags=disnake.MessageFlags(is_components_v2=True)
            )
        else:
            return await inter.edit_original_message(
                embed=None,
                components=components
            )
    
    @staticmethod
    async def success(inter: disnake.MessageInteraction, message: str, send=False, followup=False, component=None) -> disnake.Message:
        components = [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"✅ {message}"),
            )
        ]
        if component:
            if isinstance(component, (list, tuple)):
                components.extend(component)
            else:
                components.append(component)

        if send:
            return await inter.response.send_message(
                components=components,
                ephemeral=True,
                flags=disnake.MessageFlags(is_components_v2=True)
            )
        elif followup:
            return await inter.followup.send(
                components=components,
                ephemeral=True,
                flags=disnake.MessageFlags(is_components_v2=True)
            )
        else:
            return await inter.edit_original_message(
                embed=None,
                components=components
            )

class embed_message:
    @staticmethod
    async def wait(inter: disnake.MessageInteraction, send=False, ephemeral=True, followup=False) -> disnake.Message:
        content = f"{emoji.loading} Carregando informações..."
        if send:
            return await inter.response.send_message(content=content, ephemeral=ephemeral)
        elif followup:
            return await inter.followup.send(content=content, ephemeral=ephemeral)
        else:
            if not inter.response.is_done():
                await inter.response.defer(with_message=False)
            # Não usar 'content' ao editar mensagens, para compatibilidade com components v2
            embed = disnake.Embed(description=content)
            return await inter.edit_original_message(embed=embed, components=[])

    @staticmethod
    async def missing_perms(inter: disnake.MessageInteraction) -> disnake.Message:
        content = "🔒 Você não tem permissão para usar este comando."
        return await inter.response.send_message(content=content, ephemeral=True)

    @staticmethod
    async def error(inter: disnake.MessageInteraction, message: str, send=False, followup=False, component=None) -> disnake.Message:
        content = f"❌ {message}"
        
        if send:
            return await inter.response.send_message(content=content, ephemeral=True, components=component)
        elif followup:
            return await inter.followup.send(content=content, ephemeral=True, components=component)
        else:
            # Evitar 'content' em edição
            embed = disnake.Embed(description=content)
            return await inter.edit_original_message(embed=embed, components=component)
            
    @staticmethod
    async def success(inter: disnake.MessageInteraction, message: str, send=False, followup=False, component=None) -> disnake.Message:
        content = f"✅ {message}"
        
        if send:
            return await inter.response.send_message(content=content, ephemeral=True, components=component)
        elif followup:
            return await inter.followup.send(content=content, ephemeral=True, components=component)
        else:
            # Evitar 'content' em edição
            embed = disnake.Embed(description=content)
            return await inter.edit_original_message(embed=embed, components=component)

    @staticmethod
    async def plain(inter: disnake.MessageInteraction, content: str, send=False, followup=False, component=None) -> disnake.Message:
        if send:
            return await inter.response.send_message(content=content, ephemeral=True, components=component)
        elif followup:
            return await inter.followup.send(content=content, ephemeral=True, components=component)
        else:
            # Evitar 'content' em edição
            embed = disnake.Embed(description=content)
            return await inter.edit_original_message(embed=embed, components=component)