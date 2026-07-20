from __future__ import annotations

import io
import re
import aiohttp
import disnake
from disnake.ext import commands

from functions.database import database as db
from functions.emoji import emoji
from functions.interaction_runtime import respond_panel, respond_error


def _em(name, fallback):
    return getattr(emoji, name, None) or fallback


def _colors():
    data = db.get_document("custom_colors") or {}
    kwargs = {}
    if data.get("primary"):
        try: kwargs["accent_colour"] = disnake.Colour(int(str(data["primary"]).replace("#", ""), 16))
        except Exception: pass
    return kwargs


def _base(title, body, *rows):
    container = disnake.ui.Container(
        disnake.ui.TextDisplay(f"# {_em('zenyx2', 'Z')}\n-# Painel > Configurações > **{title}**"),
        disnake.ui.Separator(),
        disnake.ui.TextDisplay(body),
        disnake.ui.Separator(),
        *rows,
        **_colors(),
    )
    return [container, disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=_em('back','↩️'), custom_id="Painel_Configuracoes"))]


def moderation_panel():
    cargos = db.get_document("cargos") or {}
    welcome = db.get_document("welcome_config") or {}
    role = f"<@&{cargos['cargo_auto_role']}>" if cargos.get("cargo_auto_role") else "`Não definido`"
    channel = f"<#{welcome['channel_id']}>" if welcome.get("channel_id") else "`Canal do sistema`"
    body = (
        "## AutoRole — Cargos Automáticos\n"
        f"**Cargo ao entrar:** {role}\n"
        f"**Boas-vindas:** `{'Ativada' if welcome.get('enabled') else 'Desativada'}`\n"
        f"**Destino:** {channel}\n"
        f"**Excluir após:** `{welcome.get('delete_after', 0)} segundos`"
    )
    return _base("Moderação", body,
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Adicionar Cargo Ao Entrar", style=disnake.ButtonStyle.grey, emoji=_em('role','🛡️'), custom_id="RefSettings_AutoRole"),
            disnake.ui.Button(label="Editar Boas Vindas", style=disnake.ButtonStyle.grey, emoji=_em('edit','✏️'), custom_id="RefSettings_Welcome"),
        )
    )


def notifications_panel():
    cfg = db.get_document("telegram_notifications") or {}
    body = (
        "## Telegram\n"
        "Receba notificações administrativas diretamente no Telegram.\n\n"
        f"**Status:** `{'Ativado' if cfg.get('enabled') else 'Desativado'}`\n"
        f"**Chat ID:** `{cfg.get('chat_id') or 'Não definido'}`"
    )
    return _base("Notificações > Telegram", body,
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Desligar Notificações" if cfg.get('enabled') else "Ligar Notificações", style=disnake.ButtonStyle.red if cfg.get('enabled') else disnake.ButtonStyle.green, emoji=_em('telegram','📨'), custom_id="RefSettings_TelegramToggle"),
            disnake.ui.Button(label="Definir Chat ID", style=disnake.ButtonStyle.grey, emoji=_em('config','⚙️'), custom_id="RefSettings_TelegramChat"),
        )
    )


def bot_panel(bot):
    info = db.get_document("custom_info") or {}
    status = db.get_document("custom_status") or {}
    colors = db.get_document("custom_colors") or {}
    bot_name = getattr(getattr(bot, "user", None), "name", None) or info.get("name") or "ZYNEX SYSTEM"
    names = status.get("names") or []
    status_text = names[0] if names else "Não definido"
    body = (
        f"**Nome atual:** `{bot_name}`\n"
        f"**Cor padrão:** `{colors.get('primary', '#4B1076')}`\n"
        f"**Status:** `{status_text}`\n"
        f"**Avatar:** `{'Configurado' if info.get('avatar_url') else 'Aplicação Discord'}`\n"
        f"**Banner:** `{'Configurado' if info.get('banner_url') else 'Não definido'}`\n"
        f"**Miniatura do painel:** `{'Configurada' if info.get('thumbnail') else 'Não definida'}`"
    )
    return _base("Configurar Bot", body,
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Alterar Nome", style=disnake.ButtonStyle.grey, emoji=_em('edit','✏️'), custom_id="RefSettings_BotName"),
            disnake.ui.Button(label="Alterar Avatar", style=disnake.ButtonStyle.grey, emoji=_em('member','👤'), custom_id="RefSettings_BotAvatar"),
            disnake.ui.Button(label="Cor Padrão", style=disnake.ButtonStyle.grey, emoji=_em('colors','🎨'), custom_id="RefSettings_BotColor"),
        ),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Alterar Status", style=disnake.ButtonStyle.grey, emoji=_em('online','🟢'), custom_id="RefSettings_BotStatus"),
            disnake.ui.Button(label="Alterar Banner", style=disnake.ButtonStyle.grey, emoji=_em('image','🖼️'), custom_id="RefSettings_BotBanner"),
            disnake.ui.Button(label="Alterar Miniatura do Painel", style=disnake.ButtonStyle.grey, emoji=_em('image','🖼️'), custom_id="RefSettings_BotThumbnail"),
        )
    )


def messages_panel():
    cfg = db.get_document("canais") or {}

    def channel(key):
        value = cfg.get(key)
        return f"<#{value}>" if value else "`Não configurado`"

    body = (
        "Configure os canais de logs e as mensagens automáticas do seu servidor.\n\n"
        f"{_em('cart','🛒')} **Compras**\n"
        "-# Canal de logs onde são enviadas todas as compras realizadas\n"
        f"Canal atual: {channel('canal_de_evento_de_compras')}\n\n"
        f"{_em('mail2','📩')} **DMs**\n"
        "-# Canal de logs onde são enviadas todas as mensagens privadas\n"
        f"Canal atual: {channel('canal_de_logs_de_dms')}\n\n"
        f"{_em('star','⭐')} **Feedbacks**\n"
        "-# Canal de logs onde são enviados todos os feedbacks\n"
        f"Canal atual: {channel('canal_de_feedback')}\n\n"
        f"{_em('wallet','💼')} **Saques**\n"
        "-# Canal de logs onde são enviados todos os saques\n"
        f"Canal atual: {channel('canal_de_logs_de_saques')}\n\n"
        f"{_em('dollar','💰')} **Saldo Adicionado**\n"
        "-# Canal de logs onde são enviados todos os saldos adicionados\n"
        f"Canal atual: {channel('canal_de_logs_de_saldo_adicionado')}"
    )
    return _base(
        "Configurar Mensagens",
        body,
        disnake.ui.ActionRow(
            disnake.ui.Button(
                label="Editar canais",
                style=disnake.ButtonStyle.grey,
                emoji=_em('edit','✏️'),
                custom_id="RefSettings_MessageChannels",
            )
        ),
    )

def message_channels_choice_panel():
    options = [
        disnake.SelectOption(label="Compras", value="canal_de_evento_de_compras", description="Logs de compras realizadas", emoji=_em('cart','🛒')),
        disnake.SelectOption(label="DMs", value="canal_de_logs_de_dms", description="Logs das mensagens privadas", emoji=_em('mail2','📩')),
        disnake.SelectOption(label="Feedbacks", value="canal_de_feedback", description="Logs de feedbacks", emoji=_em('star','⭐')),
        disnake.SelectOption(label="Saques", value="canal_de_logs_de_saques", description="Logs de solicitações de saque", emoji=_em('wallet','💼')),
        disnake.SelectOption(label="Saldo Adicionado", value="canal_de_logs_de_saldo_adicionado", description="Logs de saldo adicionado", emoji=_em('dollar','💰')),
    ]
    return _base(
        "Configurar Mensagens > Editar Canais",
        "Selecione abaixo qual canal de logs deseja configurar.",
        disnake.ui.ActionRow(
            disnake.ui.StringSelect(
                custom_id="RefSettings_MessageChannelChoice",
                placeholder="Selecione um canal de logs",
                min_values=1,
                max_values=1,
                options=options,
            )
        ),
    )


def channels_panel():
    cfg = db.get_document("canais") or {}
    cart_cfg = db.get_document("cart_channels") or {}
    values = [
        ("Pedidos (Admin)", cfg.get("canal_de_logs_de_pedidos")),
        ("Pedidos (Público)", cfg.get("canal_de_evento_de_compras")),
        ("Categoria de Carrinhos", cart_cfg.get("category_id")),
        ("Entradas", cfg.get("canal_de_logs_de_entradas")),
        ("Saídas", cfg.get("canal_de_logs_de_saidas")),
        ("Convites", cfg.get("canal_de_logs_de_convites")),
    ]
    body = "\n".join(f"**{name}:** {f'<#{value}>' if value else '`Não definido`'}" for name, value in values)
    options = [
        disnake.SelectOption(label="Canal de Pedidos (Admin)", value="orders_admin", emoji=_em('textc','#')),
        disnake.SelectOption(label="Canal de Pedidos (Público)", value="orders_public", emoji=_em('announcement','📢')),
        disnake.SelectOption(label="Categoria de Carrinhos", value="cart_category", emoji=_em('folder','📁')),
        disnake.SelectOption(label="Canal de Entradas", value="joins", emoji=_em('member','👤')),
        disnake.SelectOption(label="Canal de Saídas", value="leaves", emoji=_em('member','👤')),
        disnake.SelectOption(label="Canal de Convites", value="invites", emoji=_em('link','🔗')),
    ]
    return _base("Configurar Canais", body,
        disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id="RefSettings_ChannelChoice", placeholder="Selecione um canal para configurar", options=options)),
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Desativar Logs Carrinhos", style=disnake.ButtonStyle.red, emoji=_em('off','🔴'), custom_id="RefSettings_DisableCartLogs"),
            disnake.ui.Button(label="Criar Tudo", style=disnake.ButtonStyle.green, emoji=_em('plus','➕'), custom_id="RefSettings_CreateChannels"),
        )
    )


def roles_panel():
    cfg = db.get_document("cargos") or {}
    client = f"<@&{cfg['cargo_cliente']}>" if cfg.get("cargo_cliente") else "`Não definido`"
    admin = f"<@&{cfg['cargo_admin']}>" if cfg.get("cargo_admin") else "`Não definido`"
    support = f"<@&{cfg['cargo_suporte']}>" if cfg.get("cargo_suporte") else "`Não definido`"
    body = f"**Cargo de Cliente:** {client}\n**Cargo de Administrador:** {admin}\n**Cargo de Suporte:** {support}"
    return _base("Configurar Cargos", body,
        disnake.ui.ActionRow(
            disnake.ui.Button(label="Cargo de Cliente", style=disnake.ButtonStyle.grey, emoji=_em('member','👤'), custom_id="RefSettings_RoleClient"),
            disnake.ui.Button(label="Cargo de Administrador", style=disnake.ButtonStyle.grey, emoji=_em('shield','🛡️'), custom_id="RefSettings_RoleAdmin"),
            disnake.ui.Button(label="Cargo de Suporte", style=disnake.ButtonStyle.grey, emoji=_em('ticket','🎫'), custom_id="RefSettings_RoleSupport"),
        ),
        disnake.ui.ActionRow(disnake.ui.Button(label="Criar Cargos Automáticos", style=disnake.ButtonStyle.green, emoji=_em('plus','➕'), custom_id="RefSettings_CreateRoles"))
    )


class AutoRoleModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog=cog
        super().__init__(title="Adicionar Cargo Ao Entrar", custom_id="RefSettings_AutoRoleModal", components=[disnake.ui.Label(text="Cargo Automático", component=disnake.ui.RoleSelect(custom_id="ref_auto_role", placeholder="Selecione o cargo", min_values=1, max_values=1))])
    async def callback(self, inter):
        value=(getattr(inter,"resolved_values",{}) or {}).get("ref_auto_role")
        if isinstance(value,(list,tuple)): value=value[0] if value else None
        value=getattr(value,"id",value)
        try: value=int(value)
        except Exception: return await respond_error(inter,"Selecione um cargo válido.")
        data=db.get_document("cargos") or {}; data["cargo_auto_role"]=value; db.save_document("cargos",data)
        await self.cog.show(inter,"moderacao")


class WelcomeModal(disnake.ui.Modal):
    def __init__(self,cog):
        self.cog=cog; cfg=db.get_document("welcome_config") or {}
        super().__init__(title="Editar Boas Vindas", custom_id="RefSettings_WelcomeModal", components=[
            disnake.ui.TextInput(label="Mensagem de boas-vindas", custom_id="message", style=disnake.TextInputStyle.paragraph, value=cfg.get("message","Bem-vindo(a), {user}!"), max_length=1800),
            disnake.ui.TextInput(label="Tempo para apagar (segundos)", custom_id="delete_after", value=str(cfg.get("delete_after",0)), max_length=6),
            disnake.ui.TextInput(label="ID do canal de destino (0 = sistema)", custom_id="channel_id", value=str(cfg.get("channel_id") or 0), max_length=20),
        ])
    async def callback(self,inter):
        try: delete_after=max(0,int(inter.text_values["delete_after"])); channel_id=int(inter.text_values["channel_id"] or 0)
        except ValueError: return await respond_error(inter,"Tempo ou canal inválido.")
        db.save_document("welcome_config",{"enabled":True,"message":inter.text_values["message"],"delete_after":delete_after,"channel_id":channel_id or None})
        await self.cog.show(inter,"moderacao")


class TextValueModal(disnake.ui.Modal):
    def __init__(self,cog,kind,title,label,current="",paragraph=False):
        self.cog=cog; self.kind=kind
        super().__init__(title=title, custom_id=f"RefSettings_Text:{kind}", components=[disnake.ui.TextInput(label=label, custom_id="value", value=str(current or ""), style=disnake.TextInputStyle.paragraph if paragraph else disnake.TextInputStyle.short, max_length=1800 if paragraph else 500)])
    async def callback(self,inter):
        value=inter.text_values["value"].strip()
        if self.kind=="telegram_chat":
            cfg=db.get_document("telegram_notifications") or {}; cfg["chat_id"]=value; db.save_document("telegram_notifications",cfg); return await self.cog.show(inter,"notificacoes")
        if self.kind=="bot_color":
            if not re.fullmatch(r"#?[0-9a-fA-F]{6}",value): return await respond_error(inter,"Use uma cor hexadecimal, por exemplo `#4B1076`.")
            if not value.startswith("#"): value="#"+value
            cfg=db.get_document("custom_colors") or {}; cfg["primary"]=value.upper(); db.save_document("custom_colors",cfg); return await self.cog.show(inter,"configurar_bot")
        if self.kind=="bot_status":
            db.save_document("custom_status",{"type":"online","names":[value]})
            try: await self.cog.bot.change_presence(activity=disnake.Game(name=value),status=disnake.Status.online)
            except Exception: pass
            return await self.cog.show(inter,"configurar_bot")
        if self.kind in {"bot_name","bot_avatar","bot_banner","bot_thumbnail"}:
            info=db.get_document("custom_info") or {}
            field={"bot_name":"name","bot_avatar":"avatar_url","bot_banner":"banner_url","bot_thumbnail":"thumbnail"}[self.kind]
            info[field]=value; db.save_document("custom_info",info)
            if self.kind=="bot_name":
                try: await self.cog.bot.user.edit(username=value)
                except Exception: pass
            elif self.kind in {"bot_avatar","bot_banner"} and value:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(value,timeout=15) as r:
                            if r.status==200:
                                raw=await r.read()
                                kwargs={"avatar":raw} if self.kind=="bot_avatar" else {"banner":raw}
                                await self.cog.bot.user.edit(**kwargs)
                except Exception: pass
            return await self.cog.show(inter,"configurar_bot")


class RoleModal(disnake.ui.Modal):
    def __init__(self,cog,key,title):
        self.cog=cog; self.key=key
        super().__init__(title=title, custom_id=f"RefSettings_RoleModal:{key}", components=[disnake.ui.Label(text=title, component=disnake.ui.RoleSelect(custom_id="ref_role", placeholder="Selecione o cargo", min_values=1,max_values=1))])
    async def callback(self,inter):
        value=(getattr(inter,"resolved_values",{}) or {}).get("ref_role")
        if isinstance(value,(list,tuple)): value=value[0] if value else None
        value=getattr(value,"id",value)
        try:value=int(value)
        except Exception:return await respond_error(inter,"Selecione um cargo válido.")
        cfg=db.get_document("cargos") or {}; cfg[self.key]=value; db.save_document("cargos",cfg); await self.cog.show(inter,"cargos")


class ChannelModal(disnake.ui.Modal):
    def __init__(self,cog,key,title,category=False,return_section="canais"):
        self.cog=cog; self.key=key; self.return_section=return_section
        types=[disnake.ChannelType.category] if category else [disnake.ChannelType.text,disnake.ChannelType.news]
        super().__init__(title=title, custom_id=f"RefSettings_ChannelModal:{key}", components=[disnake.ui.Label(text=title,component=disnake.ui.ChannelSelect(custom_id="ref_channel",placeholder="Selecione",channel_types=types,min_values=1,max_values=1))])
    async def callback(self,inter):
        value=(getattr(inter,"resolved_values",{}) or {}).get("ref_channel")
        if isinstance(value,(list,tuple)): value=value[0] if value else None
        value=getattr(value,"id",value)
        try:value=int(value)
        except Exception:return await respond_error(inter,"Selecione um canal válido.")
        if self.key=="category_id":
            cfg=db.get_document("cart_channels") or {}; cfg[self.key]=value; db.save_document("cart_channels",cfg)
        else:
            cfg=db.get_document("canais") or {}; cfg[self.key]=value; db.save_document("canais",cfg)
        await self.cog.show(inter,self.return_section)


class SettingsReferenceCog(commands.Cog):
    def __init__(self,bot): self.bot=bot

    async def show(self,inter,section):
        mapping={
            "moderacao": moderation_panel,
            "notificacoes": notifications_panel,
            "configurar_bot": lambda: bot_panel(self.bot),
            "mensagens": messages_panel,
            "canais": channels_panel,
            "cargos": roles_panel,
        }
        builder=mapping.get(section)
        if not builder:return await respond_error(inter,"Seção de configuração não encontrada.")
        return await respond_panel(inter,{"components":builder()},prefer_edit=True)

    @commands.Cog.listener("on_button_click")
    async def buttons(self,inter):
        cid=getattr(inter.component,"custom_id","") or ""
        if not cid.startswith("RefSettings_"):return
        if cid=="RefSettings_AutoRole":return await inter.response.send_modal(AutoRoleModal(self))
        if cid=="RefSettings_Welcome":return await inter.response.send_modal(WelcomeModal(self))
        if cid=="RefSettings_TelegramToggle":
            cfg=db.get_document("telegram_notifications") or {}; cfg["enabled"]=not bool(cfg.get("enabled")); db.save_document("telegram_notifications",cfg); return await self.show(inter,"notificacoes")
        if cid=="RefSettings_TelegramChat":return await inter.response.send_modal(TextValueModal(self,"telegram_chat","Definir Chat ID","Chat ID",(db.get_document("telegram_notifications") or {}).get("chat_id","")))
        if cid=="RefSettings_BotName":return await inter.response.send_modal(TextValueModal(self,"bot_name","Alterar Nome do BOT","Novo nome",getattr(getattr(self.bot,"user",None),"name","")))
        if cid=="RefSettings_BotAvatar":return await inter.response.send_modal(TextValueModal(self,"bot_avatar","Alterar Avatar Do BOT","URL do avatar",(db.get_document("custom_info") or {}).get("avatar_url","")))
        if cid=="RefSettings_BotColor":return await inter.response.send_modal(TextValueModal(self,"bot_color","Alterar Cor Padrão","Cor hexadecimal",(db.get_document("custom_colors") or {}).get("primary","#4B1076")))
        if cid=="RefSettings_BotStatus":return await inter.response.send_modal(TextValueModal(self,"bot_status","Alterar Status do seu BOT","Texto do status",((db.get_document("custom_status") or {}).get("names") or [""])[0]))
        if cid=="RefSettings_BotBanner":return await inter.response.send_modal(TextValueModal(self,"bot_banner","Alterar Banner Do BOT","URL do banner",(db.get_document("custom_info") or {}).get("banner_url","")))
        if cid=="RefSettings_BotThumbnail":return await inter.response.send_modal(TextValueModal(self,"bot_thumbnail","Alterar Miniatura do Painel","URL da miniatura",(db.get_document("custom_info") or {}).get("thumbnail","")))
        if cid=="RefSettings_MessageChannels":
            return await respond_panel(inter,{"components":message_channels_choice_panel()},prefer_edit=True)
        if cid=="RefSettings_DisableCartLogs":
            cfg=db.get_document("cart_channels") or {}; cfg["logs_enabled"]=False; db.save_document("cart_channels",cfg); return await self.show(inter,"canais")
        if cid=="RefSettings_CreateChannels":
            if not inter.guild:return await respond_error(inter,"Use esta opção dentro de um servidor.")
            await inter.response.defer(ephemeral=True)
            cfg=db.get_document("canais") or {}; cart=db.get_document("cart_channels") or {}
            try:
                category=inter.guild.get_channel(int(cart.get("category_id",0))) if cart.get("category_id") else None
                if category is None: category=await inter.guild.create_category("🛒 CARRINHOS")
                cart["category_id"]=category.id; cart["logs_enabled"]=True
                specs=[("canal_de_logs_de_pedidos","📦-pedidos-admin"),("canal_de_evento_de_compras","🛍️-compras-aprovadas"),("canal_de_logs_de_entradas","📥-entradas"),("canal_de_logs_de_saidas","📤-saidas"),("canal_de_logs_de_convites","🔗-convites")]
                for key,name in specs:
                    if not cfg.get(key): cfg[key]=(await inter.guild.create_text_channel(name)).id
                db.save_document("canais",cfg);db.save_document("cart_channels",cart)
                await inter.followup.send(f"{_em('correct','✅')} Canais criados e configurados.",ephemeral=True)
            except Exception as exc:return await inter.followup.send(f"{_em('wrong','❌')} Não foi possível criar todos os canais: `{type(exc).__name__}`.",ephemeral=True)
            return
        if cid=="RefSettings_RoleClient":return await inter.response.send_modal(RoleModal(self,"cargo_cliente","Cargo de Cliente"))
        if cid=="RefSettings_RoleAdmin":return await inter.response.send_modal(RoleModal(self,"cargo_admin","Cargo de Administrador"))
        if cid=="RefSettings_RoleSupport":return await inter.response.send_modal(RoleModal(self,"cargo_suporte","Cargo de Suporte"))
        if cid=="RefSettings_CreateRoles":
            if not inter.guild:return await respond_error(inter,"Use esta opção dentro de um servidor.")
            await inter.response.defer(ephemeral=True)
            cfg=db.get_document("cargos") or {}
            try:
                for key,name in (("cargo_cliente","Cliente"),("cargo_admin","Administrador da Loja"),("cargo_suporte","Suporte")):
                    if not cfg.get(key):cfg[key]=(await inter.guild.create_role(name=name,reason="Configuração automática ZENYX")).id
                db.save_document("cargos",cfg);await inter.followup.send(f"{_em('correct','✅')} Cargos criados e configurados.",ephemeral=True)
            except Exception as exc:await inter.followup.send(f"{_em('wrong','❌')} Falha ao criar cargos: `{type(exc).__name__}`.",ephemeral=True)

    @commands.Cog.listener("on_dropdown")
    async def dropdown(self,inter):
        custom_id = getattr(inter.component,"custom_id","")
        if custom_id == "RefSettings_MessageChannelChoice":
            choice = inter.values[0]
            titles = {
                "canal_de_evento_de_compras": "Canal de Compras",
                "canal_de_logs_de_dms": "Canal de DMs",
                "canal_de_feedback": "Canal de Feedbacks",
                "canal_de_logs_de_saques": "Canal de Saques",
                "canal_de_logs_de_saldo_adicionado": "Canal de Saldo Adicionado",
            }
            return await inter.response.send_modal(
                ChannelModal(self, choice, titles.get(choice, "Canal de Logs"), False, "mensagens")
            )
        if custom_id != "RefSettings_ChannelChoice":
            return
        choice=inter.values[0]
        mapping={
            "orders_admin":("canal_de_logs_de_pedidos","Canal de Pedidos (Admin)",False),
            "orders_public":("canal_de_evento_de_compras","Canal de Pedidos (Público)",False),
            "cart_category":("category_id","Categoria de Carrinhos",True),
            "joins":("canal_de_logs_de_entradas","Canal de Entradas",False),
            "leaves":("canal_de_logs_de_saidas","Canal de Saídas",False),
            "invites":("canal_de_logs_de_convites","Canal de Convites",False),
        }
        key,title,category=mapping[choice]
        return await inter.response.send_modal(ChannelModal(self,key,title,category))


def setup(bot):bot.add_cog(SettingsReferenceCog(bot))
