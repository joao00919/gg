import disnake
from functions.emoji import emoji

# Ordem, nomes e descrições iguais ao painel do atendente exibido na referência.
TEAM_BUTTONS = {
    "close": {"label": "Fechar Ticket", "emoji": emoji.delete, "custom_id": "ticket_close_ticket", "description": "Feche o ticket atual."},
    "assume": {"label": "Assumir Ticket", "emoji": emoji.double_check, "custom_id": "ticket_claim", "description": "Assuma o atendimento deste ticket."},
    "notify": {"label": "Notificar Usuário", "emoji": emoji.warn, "custom_id": "ticket_notify", "description": "Notifique o usuário responsável pelo ticket."},
    "rename": {"label": "Renomear Ticket", "emoji": emoji.edit, "custom_id": "ticket_rename", "description": "Altere o nome do canal ou tópico."},
    "priority": {"label": "Definir Prioridade", "emoji": emoji.coupon, "custom_id": "ticket_set_priority", "description": "Defina a prioridade do atendimento."},
    "resolved": {"label": "Resolvido", "emoji": emoji.like, "custom_id": "ticket_resolved", "description": "Marque o atendimento como resolvido."},
    "archive": {"label": "Arquivar Ticket", "emoji": emoji.dir, "custom_id": "ticket_archive", "description": "Arquive o ticket sem excluí-lo."},
    "add_user": {"label": "Adicionar Usuário", "emoji": emoji.plus, "custom_id": "ticket_add_user", "description": "Adicione outro usuário ao ticket."},
    "remove_user": {"label": "Remover Usuário", "emoji": emoji.minus, "custom_id": "ticket_remove_user", "description": "Remova um usuário do ticket."},
    "transcript": {"label": "Transcript", "emoji": emoji.receipt, "custom_id": "ticket_transcript", "description": "Gere o transcript do atendimento."},
    "history": {"label": "Histórico", "emoji": emoji.clock, "custom_id": "ticket_history", "description": "Consulte o histórico de tickets do usuário."},
    "manage_call": {"label": "Gerenciar Call", "emoji": emoji.voice, "custom_id": "ticket_create_call", "description": "Crie ou gerencie a call do ticket."},
    "transfer": {"label": "Transferir", "emoji": emoji.arrow, "custom_id": "ticket_transfer", "description": "Transfira o ticket para outro atendente."},
}


class AttendantSetupView(disnake.ui.View):
    def __init__(self, panel_data: dict, option_data: dict | None = None):
        super().__init__(timeout=None)
        panel_preferences = panel_data.get("preferences", {}) or {}
        option_preferences = option_data.get("preferences", {}) if option_data else {}
        preferences = {**panel_preferences, **option_preferences}
        team_setup = preferences.get("team_setup") or {}
        disabled_buttons = set(team_setup.get("disabled_buttons") or [])

        for key, data in TEAM_BUTTONS.items():
            if key in disabled_buttons:
                continue
            self.add_item(disnake.ui.Button(
                label=data["label"],
                style=disnake.ButtonStyle.grey,
                emoji=data["emoji"],
                custom_id=data["custom_id"],
                disabled=data.get("disabled", False),
            ))
