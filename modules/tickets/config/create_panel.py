import disnake
from functions.utils import utils
from functions.database import database as db
from functions.message import message, embed_message
from functions.emoji import emoji
from .create_options import create_options_embed, create_options_components

class CreateTicketPanelModal(disnake.ui.Modal):
    def __init__(self, inter: disnake.CommandInteraction):
        self.inter = inter
        components = [
            disnake.ui.TextInput(
                label="Nome do Painel",
                placeholder="Ex: Suporte Geral",
                custom_id="panel_name",
                max_length=50,
            ),
        ]
        super().__init__(title="Criar Novo Painel de Ticket", components=components, custom_id=f"create_ticket_modal")

    async def callback(self, inter: disnake.ModalInteraction):
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter, send=False)
        else:
            await message.wait(inter, send=False)
        
        panel_id = utils.gerar_id()
        panel_name = (inter.text_values.get("panel_name") or "").strip()

        if len(panel_name) < 2:
            return await message.error(inter, "Informe um nome com pelo menos 2 caracteres.")

        config = db.get_document("tickets_config") or {}
        if "panels" not in config:
            config["panels"] = {}

        if any(str(item.get("name", "")).strip().casefold() == panel_name.casefold() for item in config["panels"].values()):
            return await message.error(inter, "Já existe um painel de ticket com esse nome.")
            
        config["panels"][panel_id] = {
            "id": panel_id,
            "name": panel_name,
            "enabled": False,
            "mode": "channel",
            "channel_id": None,
            "category_id": None,
            "message_id": None,
            "has_pending_changes": True,
            "options": [],
            "office_hours": {"enabled": False, "start_time": None, "end_time": None, "off_days": [], "message": None},
            "preferences": {},
            "ticket_mode": "common",
            "purchase_settings": {
                "max_purchases": 25,
                "warranty_days": 30,
                "allow_without_purchase": False,
                "show_delivery_items": True
            },
            "automation": {
                "stale_minutes": 30,
                "mention_support": True,
                "raise_priority": True
            },
            "message_style": "embed",
            "button": {
                "label": "Abrir Ticket",
                "emoji": emoji.verified,
                "style": "green"
            },
            "embed": {
                "title": "Central de Atendimento",
                "description": "Clique no botão abaixo para abrir um atendimento com nossa equipe.",
                "color": "#2B2D31"
            },
            "content": {
                "content": "# Central de Atendimento\n\nClique no botão abaixo para abrir um atendimento com nossa equipe."
            },
            "container": {
                "content": "# Central de Atendimento\n\nClique no botão abaixo para abrir um atendimento com nossa equipe.",
                "color": "#2B2D31"
            },
            "messages": {
                "close_message": "Seu ticket `{channel_name}` foi fechado por {autor_mention}.",
                "close_message_reason": "Seu ticket `{channel_name}` foi fechado por {autor_mention}.\n**Motivo:** {reason}",
                "notify_message_staff_to_user": "Olá {user_mention}, você está sendo notificado sobre o seu ticket `{channel_name}`. A equipe de suporte está aguardando sua resposta.",
                "notify_message_user_to_staff": "{user_mention} está solicitando sua atenção no ticket `{channel_name}`.",
                "add_user_message": "{alvo_mention} foi adicionado a este ticket por {autor_mention}.",
                "add_user_dm_message": "Olá {alvo_mention}, você foi adicionado ao ticket `{channel_name}` por {autor_mention}.",
                "remove_user_message": "{alvo_mention} foi removido deste ticket por {autor_mention}.",
                "remove_user_dm_message": "Olá {alvo_mention}, você foi removido do ticket `{channel_name}` por {autor_mention}.",
                "assume_message": "{autor_mention} assumiu o atendimento deste ticket.",
                "assume_dm_message": "Olá {user_mention}, o atendente {autor_mention} assumiu seu ticket `{channel_name}`.",
                "transfer_message": "O ticket foi transferido por {autor_mention}.",
                "create_call_message": "Uma call de voz foi iniciada para este ticket por {autor_mention}.",
                "create_call_dm_message": "Olá! Uma call de voz foi criada para o seu ticket `{channel_name}`.",
                "request_call_message": "O usuário {autor_mention} solicitou a criação de uma call."
            }
        }
        db.save_document("tickets_config", config)
        
        mode = db.get_document("custom_mode").get("mode")

        if mode == "components":
            components = create_options_components(panel_id, panel_name, [])
            await inter.edit_original_message(components=components)
        else:
            embed, components = create_options_embed(panel_id, panel_name, [])
            await inter.edit_original_message(content=None, embed=embed, components=components)
