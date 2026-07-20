from functions.database import database as db

def carregar_config() -> dict:
    """Carrega a configuração da coleção 'automations_invite_tracker'."""
    data = db.get_document("automations_invite_tracker") or {}
    data.setdefault("ativado", False)
    data.setdefault("channel_id", None)
    data.setdefault("welcome_message", "Seja bem-vindo(a) {member}! Você foi convidado(a) por {inviter} que agora possui {invites} convites válidos.")
    data.setdefault("welcome_message_vanity", "Seja bem-vindo(a) {member}! Você entrou através do Vanity URL do servidor.")
    data.setdefault("leave_message", "Que pena, {member} nos deixou. Ele(a) foi convidado(a) por {inviter} que agora possui {invites} convites válidos.")
    return data

def salvar_config(data: dict) -> None:
    """Salva a configuração na coleção 'automations_invite_tracker'."""
    db.save_document("automations_invite_tracker", data)

def get_invites_data() -> dict:
    """Carrega os dados de convites do documento dedicado 'convites'.
    Se estiver vazio, tenta migrar de automations_invite_tracker.invites_data uma única vez.
    """
    data = db.get_document("convites") or {}
    if data:
        return data

    # Fallback de migração: mover invites_data antigo, se existir
    old_conf = db.get_document("automations_invite_tracker") or {}
    old_invites = old_conf.get("invites_data") if isinstance(old_conf, dict) else None
    if isinstance(old_invites, dict) and old_invites:
        db.save_document("convites", old_invites)
        # remove chave antiga para evitar migração repetida
        try:
            old_conf.pop("invites_data", None)
            db.save_document("automations_invite_tracker", old_conf)
        except Exception:
            pass
        return old_invites
    return {}

def save_invites_data(data: dict) -> None:
    """Salva os dados de convites no documento dedicado 'convites'."""
    db.save_document("convites", data)
