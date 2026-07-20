import disnake
from disnake.ext import commands
from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
from functions.email_utils import is_valid_email
import re

# Todos os DDDs do Brasil (para validação)
ALL_DDDS = [
    "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "21", "22", "24", "27", "28",
    "31", "32", "33", "34", "35", "37", "38",
    "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "51", "53", "54", "55",
    "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "71", "73", "74", "75", "77", "79",
    "81", "82", "83", "84", "85", "86", "87", "88", "89",
    "91", "92", "93", "94", "95", "96", "97", "98", "99"
]

class ConfigPhoneModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog = cog
        
        components = [
            disnake.ui.TextInput(
                label="DDD",
                placeholder="Ex: 11",
                custom_id="input_ddd",
                min_length=2,
                max_length=2,
                style=disnake.TextInputStyle.short
            ),
            disnake.ui.TextInput(
                label="Número de Celular",
                placeholder="99999-9999",
                custom_id="input_number",
                min_length=8,
                max_length=15,
                style=disnake.TextInputStyle.short
            )
        ]
        super().__init__(title="Configurar Celular", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter)
        else:
            await message.wait(inter)

        ddd = inter.text_values["input_ddd"]
        number = inter.text_values["input_number"]

        if ddd not in ALL_DDDS:
             await inter.followup.send(
                 f"{emoji.error} DDD inválido. Por favor, insira um DDD válido do Brasil (Ex: 11, 21, 31...).", 
                 ephemeral=True
             )
             return

        clean_number = re.sub(r"\D", "", number)
        
        if len(clean_number) < 8:
            await inter.followup.send(
                 f"{emoji.error} Número inválido. Verifique se digitou corretamente.", 
                 ephemeral=True
             )
            return

        config = self.cog.get_config()
        config["ddd"] = ddd
        config["number"] = clean_number
        config["enabled"] = True
        db.save_document("notifications_config", config)

        panel = self.cog.panel(inter, config)

        if mode == "embed":
            await inter.edit_original_message(content=None, **panel)
        else:
            await inter.edit_original_message(**panel)
            
        await inter.followup.send(
            f"{emoji.correct} Número configurado com sucesso: ({ddd}) {clean_number}",
            ephemeral=True
        )

class ConfigEmailModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog = cog
        config = db.get_document("notifications_email_config")
        
        components = [
            disnake.ui.TextInput(
                label="Email de Destino",
                placeholder="seuemail@exemplo.com",
                custom_id="email_dest",
                value=config.get("email", ""),
                style=disnake.TextInputStyle.short
            ),
            disnake.ui.TextInput(
                label="Servidor SMTP",
                placeholder="smtp.gmail.com",
                custom_id="smtp_server",
                value=config.get("smtp_server", "smtp.gmail.com"),
                style=disnake.TextInputStyle.short
            ),
            disnake.ui.TextInput(
                label="Porta SMTP",
                placeholder="587",
                custom_id="smtp_port",
                value=str(config.get("smtp_port", 587)),
                style=disnake.TextInputStyle.short
            ),
            disnake.ui.TextInput(
                label="Usuário SMTP (Email)",
                placeholder="seuemail@gmail.com",
                custom_id="smtp_user",
                value=config.get("smtp_user", ""),
                style=disnake.TextInputStyle.short
            ),
            disnake.ui.TextInput(
                label="Senha SMTP (Senha de App)",
                placeholder="sua-senha-aqui",
                custom_id="smtp_pass",
                value=config.get("smtp_pass", ""),
                style=disnake.TextInputStyle.short
            )
        ]
        super().__init__(title="Configurar Notificações por Email", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter)
        else:
            await message.wait(inter)

        email_dest = inter.text_values["email_dest"]
        smtp_server = inter.text_values["smtp_server"]
        smtp_port = inter.text_values["smtp_port"]
        smtp_user = inter.text_values["smtp_user"]
        smtp_pass = inter.text_values["smtp_pass"]

        if not is_valid_email(email_dest):
            await inter.followup.send(f"{emoji.error} Email de destino inválido.", ephemeral=True)
            return
        
        if not is_valid_email(smtp_user):
            await inter.followup.send(f"{emoji.error} Usuário SMTP deve ser um email válido.", ephemeral=True)
            return

        try:
            port = int(smtp_port)
        except ValueError:
            await inter.followup.send(f"{emoji.error} Porta SMTP deve ser um número.", ephemeral=True)
            return

        config = db.get_document("notifications_email_config")
        config.update({
            "email": email_dest,
            "smtp_server": smtp_server,
            "smtp_port": port,
            "smtp_user": smtp_user,
            "smtp_pass": smtp_pass,
            "enabled": True
        })
        db.save_document("notifications_email_config", config)

        panel = self.cog.panel(inter)
        if mode == "embed":
            await inter.edit_original_message(content=None, **panel)
        else:
            await inter.edit_original_message(**panel)
            
        await inter.followup.send(f"{emoji.correct} Configurações de email salvas com sucesso!", ephemeral=True)

class ConfigureNotifications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def get_config():
        config = db.get_document("notifications_config")
        if not config:
            config = {"enabled": False, "ddd": None, "number": None}
            db.save_document("notifications_config", config)
        return config

    @staticmethod
    def get_email_config():
        config = db.get_document("notifications_email_config")
        if not config:
            config = {
                "enabled": False,
                "email": None,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": null,
                "smtp_pass": null,
                "use_tls": True
            }
            db.save_document("notifications_email_config", config)
        return config

    @staticmethod
    def panel(inter: disnake.MessageInteraction, config: dict = None) -> dict:
        if config is None:
            config = ConfigureNotifications.get_config()
        email_config = db.get_document("notifications_email_config")
        
        enabled = config.get("enabled", False)
        email_enabled = email_config.get("enabled", False)
        
        colors = db.get_document("custom_colors")
        primary_color_hex = colors.get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        phone_info = "Nenhum número configurado"
        if config.get("ddd") and config.get("number"):
            phone_info = f"({config.get('ddd')}) {config.get('number')}"

        email_info = email_config.get("email") or "Nenhum email configurado"

        status_text = "Ativado" if enabled else "Desativado"
        status_emoji = emoji.on if enabled else emoji.off
        
        email_status_text = "Ativado" if email_enabled else "Desativado"
        email_status_emoji = emoji.on if email_enabled else emoji.off
        
        # Botões WhatsApp
        toggle_btn = disnake.ui.Button(
            label="WhatsApp: " + ("Desativar" if enabled else "Ativar"),
            style=disnake.ButtonStyle.red if enabled else disnake.ButtonStyle.green,
            emoji=emoji.whatsapp,
            custom_id="ConfigNotif_Toggle"
        )
        
        config_num_btn = disnake.ui.Button(
            label="Configurar Número",
            style=disnake.ButtonStyle.grey,
            emoji=emoji.edit,
            custom_id="ConfigNotif_ConfigNumber",
            disabled=not enabled
        )

        # Botões Email
        toggle_email_btn = disnake.ui.Button(
            label="Email: " + ("Desativar" if email_enabled else "Ativar"),
            style=disnake.ButtonStyle.red if email_enabled else disnake.ButtonStyle.green,
            emoji=emoji.mail2,
            custom_id="ConfigNotif_ToggleEmail"
        )
        
        config_email_btn = disnake.ui.Button(
            label="Configurar Email",
            style=disnake.ButtonStyle.grey,
            emoji=emoji.edit,
            custom_id="ConfigNotif_ConfigEmail",
            disabled=not email_enabled
        )
        
        back_btn = disnake.ui.Button(
            label="Voltar",
            style=disnake.ButtonStyle.grey,
            emoji=emoji.back,
            custom_id="Painel_Configuracoes"
        )

        mode = db.get_document("custom_mode").get("mode")
        
        if mode == "embed":
            embed = disnake.Embed(
                title="Configuração de Notificações",
                description=(
                    f"### {emoji.whatsapp} WhatsApp\n"
                    f"**Status:** {status_emoji} {status_text}\n"
                    f"**Número:** `{phone_info}`\n\n"
                    f"### {emoji.mail2} Email\n"
                    f"**Status:** {email_status_emoji} {email_status_text}\n"
                    f"**Email:** `{email_info}`\n\n"
                    "Configure aqui como deseja receber as notificações do sistema."
                )
            )
            if primary_color_hex:
                embed.color = container_kwargs.get("accent_colour")
                
            return {
                "embed": embed,
                "components": [
                    disnake.ui.ActionRow(toggle_btn, config_num_btn),
                    disnake.ui.ActionRow(toggle_email_btn, config_email_btn),
                    disnake.ui.ActionRow(back_btn)
                ]
            }
        else:
            return {
                "components": [
                    disnake.ui.Container(
                        disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Configurações > **Notificações**"),
                        disnake.ui.Separator(),
                        disnake.ui.TextDisplay(
                            f"### {emoji.whatsapp} WhatsApp\n"
                            f"**Status:** {status_emoji} {status_text}\n"
                            f"**Número:** `{phone_info}`\n\n"
                            f"### {emoji.mail2} Email\n"
                            f"**Status:** {email_status_emoji} {email_status_text}\n"
                            f"**Email:** `{email_info}`"
                        ),
                        disnake.ui.Separator(),
                        disnake.ui.ActionRow(toggle_btn, config_num_btn),
                        disnake.ui.ActionRow(toggle_email_btn, config_email_btn),
                        **container_kwargs
                    ),
                    disnake.ui.ActionRow(back_btn)
                ]
            }

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id.startswith("ConfigNotif_"):
            return
        
        mode = db.get_document("custom_mode").get("mode")
        async def wait():
            if mode == "embed":
                await embed_message.wait(inter)
            else:
                await message.wait(inter)
        
        async def edit(payload):
            if mode == "embed":
                await inter.edit_original_message(content=None, **payload)
            else:
                await inter.edit_original_message(**payload)

        if inter.component.custom_id == "ConfigNotif_Toggle":
            config = self.get_config()
            new_state = not config.get("enabled", False)
            config["enabled"] = new_state
            db.save_document("notifications_config", config)
            await wait()
            await edit(self.panel(inter, config))

        elif inter.component.custom_id == "ConfigNotif_ToggleEmail":
            config = db.get_document("notifications_email_config")
            new_state = not config.get("enabled", False)
            config["enabled"] = new_state
            db.save_document("notifications_email_config", config)
            await wait()
            await edit(self.panel(inter))

        elif inter.component.custom_id == "ConfigNotif_ConfigNumber":
            await inter.response.send_modal(ConfigPhoneModal(self))
            
        elif inter.component.custom_id == "ConfigNotif_ConfigEmail":
            await inter.response.send_modal(ConfigEmailModal(self))
        
        elif inter.component.custom_id == "ConfigNotif_BackToMain":
            await wait()
            await edit(self.panel(inter))

def setup(bot: commands.Bot):
    bot.add_cog(ConfigureNotifications(bot))
