from __future__ import annotations

import re
import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.interaction_runtime import respond_panel, respond_error

DOC = "protection_server"
LINK_RE = re.compile(r"(?:https?://|www\.|discord(?:app)?\.com/invite/|discord\.gg/)", re.I)


def _cfg():
    data = db.get_document(DOC) or {}
    data.setdefault("links_enabled", False)
    data.setdefault("punishment", "delete")
    data.setdefault("log_channel_id", None)
    data.setdefault("immune_role_ids", [])
    data.setdefault("immune_channel_ids", [])
    return data


def _save(data):
    db.save_document(DOC, data)


def _em(name, fallback):
    return getattr(emoji, name, None) or fallback


class LogChannelModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog = cog
        super().__init__(
            title="Canal de Logs",
            custom_id="ProtectionServer_LogModal",
            components=[
                disnake.ui.Label(
                    text="Canal de Logs",
                    description="Selecione onde os eventos de proteção serão registrados.",
                    component=disnake.ui.ChannelSelect(
                        custom_id="protection_server_log_channel",
                        placeholder="Selecione um canal de texto",
                        channel_types=[disnake.ChannelType.text],
                        min_values=1,
                        max_values=1,
                    ),
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        values = getattr(inter, "resolved_values", {}) or {}
        selected = values.get("protection_server_log_channel")
        if isinstance(selected, (list, tuple)):
            selected = selected[0] if selected else None
        channel_id = getattr(selected, "id", selected)
        try:
            channel_id = int(channel_id)
        except Exception:
            return await respond_error(inter, "Selecione um canal válido.")
        data = _cfg(); data["log_channel_id"] = channel_id; _save(data)
        await self.cog.display_panel(inter)


class ImmuneRolesModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog = cog
        super().__init__(
            title="Cargos Imunes",
            custom_id="ProtectionServer_RolesModal",
            components=[
                disnake.ui.Label(
                    text="Cargos Imunes",
                    description="Membros com estes cargos não serão punidos.",
                    component=disnake.ui.RoleSelect(
                        custom_id="protection_server_immune_roles",
                        placeholder="Selecione até 10 cargos",
                        min_values=0,
                        max_values=10,
                        required=False,
                    ),
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        values = getattr(inter, "resolved_values", {}) or {}
        selected = values.get("protection_server_immune_roles") or []
        if not isinstance(selected, (list, tuple)):
            selected = [selected]
        ids = []
        for item in selected:
            value = getattr(item, "id", item)
            try: ids.append(int(value))
            except Exception: pass
        data = _cfg(); data["immune_role_ids"] = ids; _save(data)
        await self.cog.display_panel(inter)


class ImmuneChannelsModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog = cog
        super().__init__(
            title="Canais Imunes",
            custom_id="ProtectionServer_ChannelsModal",
            components=[
                disnake.ui.Label(
                    text="Canais Imunes",
                    description="Links enviados nestes canais serão permitidos.",
                    component=disnake.ui.ChannelSelect(
                        custom_id="protection_server_immune_channels",
                        placeholder="Selecione até 10 canais",
                        channel_types=[disnake.ChannelType.text, disnake.ChannelType.news],
                        min_values=0,
                        max_values=10,
                        required=False,
                    ),
                )
            ],
        )

    async def callback(self, inter: disnake.ModalInteraction):
        values = getattr(inter, "resolved_values", {}) or {}
        selected = values.get("protection_server_immune_channels") or []
        if not isinstance(selected, (list, tuple)):
            selected = [selected]
        ids = []
        for item in selected:
            value = getattr(item, "id", item)
            try: ids.append(int(value))
            except Exception: pass
        data = _cfg(); data["immune_channel_ids"] = ids; _save(data)
        await self.cog.display_panel(inter)


class ServidorProtectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def panel_components(self):
        data = _cfg()
        colors = db.get_document("custom_colors") or {}
        kwargs = {}
        if colors.get("primary"):
            try: kwargs["accent_colour"] = disnake.Colour(int(str(colors["primary"]).replace("#", ""), 16))
            except Exception: pass
        log = f"<#{data['log_channel_id']}>" if data.get("log_channel_id") else "`Não definido`"
        roles = " ".join(f"<@&{x}>" for x in data.get("immune_role_ids", [])) or "`Nenhum`"
        channels = " ".join(f"<#{x}>" for x in data.get("immune_channel_ids", [])) or "`Nenhum`"
        enabled = bool(data.get("links_enabled"))
        punishment = data.get("punishment", "delete")
        punishment_names = {"delete": "Nenhuma Ação (Apagar Mensagem)", "ban": "Banir Usuário", "kick": "Expulsar Usuário", "remove_roles": "Remover todos os cargos do Usuário"}
        details = (
            f"{_em('power', '⏻')} **Status:** `{'Ativado' if enabled else 'Desativado'}`\n"
            f"{_em('textc', '📝')} **Canal de Logs:** {log}\n"
            f"{_em('role', '🛡️')} **Cargos Imunes:** {roles}\n"
            f"{_em('textc', '#')} **Canais Imunes:** {channels}\n"
            f"{_em('ban', '🔨')} **Punição:** `{punishment_names.get(punishment, punishment)}`"
        )
        options = [
            disnake.SelectOption(label="Nenhuma Ação (Apagar Mensagem)", value="delete", emoji=_em('delete', '🗑️'), default=punishment == "delete"),
            disnake.SelectOption(label="Banir Usuário", value="ban", emoji=_em('ban', '🔨'), default=punishment == "ban"),
            disnake.SelectOption(label="Expulsar Usuário", value="kick", emoji=_em('wrong', '❌'), default=punishment == "kick"),
            disnake.SelectOption(label="Remover todos os cargos do Usuário", value="remove_roles", emoji=_em('role', '🛡️'), default=punishment == "remove_roles"),
        ]
        container = disnake.ui.Container(
            disnake.ui.TextDisplay(f"# {_em('zenyx2', 'Z')}\n-# Painel > Proteção > Proteção Geral > **Servidor**"),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay("## Proteção de Links\nBloqueia links e convites não autorizados no servidor."),
            disnake.ui.Separator(),
            disnake.ui.TextDisplay(details),
            disnake.ui.Separator(),
            disnake.ui.ActionRow(disnake.ui.Button(label="Ativar Proteção de Links" if not enabled else "Desativar Proteção de Links", style=disnake.ButtonStyle.green if not enabled else disnake.ButtonStyle.red, emoji=_em('shield', '🛡️'), custom_id="ProtectionServer_Toggle")),
            disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id="ProtectionServer_Punishment", placeholder="Selecione a punição aplicada", options=options)),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Canal de Logs", style=disnake.ButtonStyle.grey, emoji=_em('textc', '📝'), custom_id="ProtectionServer_Logs"),
                disnake.ui.Button(label="Cargos Imunes", style=disnake.ButtonStyle.grey, emoji=_em('role', '🛡️'), custom_id="ProtectionServer_Roles"),
                disnake.ui.Button(label="Canais Imunes", style=disnake.ButtonStyle.grey, emoji=_em('textc', '#'), custom_id="ProtectionServer_Channels"),
            ),
            **kwargs,
        )
        return [container, disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=_em('back', '↩️'), custom_id="Back_To_Protection_Geral"))]

    async def display_panel(self, inter):
        return await respond_panel(inter, {"components": self.panel_components()}, prefer_edit=True)

    @commands.Cog.listener("on_button_click")
    async def buttons(self, inter: disnake.MessageInteraction):
        cid = getattr(inter.component, "custom_id", "") or ""
        if not cid.startswith("ProtectionServer_"):
            return
        if cid == "ProtectionServer_Toggle":
            data = _cfg(); data["links_enabled"] = not bool(data.get("links_enabled")); _save(data)
            return await self.display_panel(inter)
        if cid == "ProtectionServer_Logs":
            return await inter.response.send_modal(LogChannelModal(self))
        if cid == "ProtectionServer_Roles":
            return await inter.response.send_modal(ImmuneRolesModal(self))
        if cid == "ProtectionServer_Channels":
            return await inter.response.send_modal(ImmuneChannelsModal(self))

    @commands.Cog.listener("on_dropdown")
    async def dropdown(self, inter: disnake.MessageInteraction):
        if getattr(inter.component, "custom_id", "") != "ProtectionServer_Punishment":
            return
        data = _cfg(); data["punishment"] = inter.values[0]; _save(data)
        return await self.display_panel(inter)

    @commands.Cog.listener("on_message")
    async def protect_links(self, msg: disnake.Message):
        if not msg.guild or not msg.author or getattr(msg.author, "bot", False):
            return
        data = _cfg()
        if not data.get("links_enabled") or not LINK_RE.search(msg.content or ""):
            return
        if msg.channel.id in set(data.get("immune_channel_ids", [])):
            return
        member = msg.author if isinstance(msg.author, disnake.Member) else None
        if member:
            if member.guild_permissions.administrator or member.id == msg.guild.owner_id:
                return
            immune = set(data.get("immune_role_ids", []))
            if any(role.id in immune for role in member.roles):
                return
        try: await msg.delete()
        except Exception: pass
        action = data.get("punishment", "delete")
        try:
            if member and action == "ban":
                await msg.guild.ban(member, reason="Proteção de links ZENYX")
            elif member and action == "kick":
                await member.kick(reason="Proteção de links ZENYX")
            elif member and action == "remove_roles":
                removable = [r for r in member.roles if not r.is_default() and not r.managed and msg.guild.me and r < msg.guild.me.top_role]
                if removable: await member.remove_roles(*removable, reason="Proteção de links ZENYX")
        except Exception:
            pass
        log_id = data.get("log_channel_id")
        if log_id:
            channel = msg.guild.get_channel(int(log_id))
            if channel:
                try:
                    await channel.send(f"{_em('shield', '🛡️')} Link bloqueado de {member.mention if member else msg.author}. Ação: `{action}`.")
                except Exception:
                    pass


def setup(bot):
    bot.add_cog(ServidorProtectionCog(bot))
