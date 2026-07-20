from functions.database import database as db
import uuid

def carregar_config() -> dict:
    """Carrega a configuração da coleção 'msg_auto'."""
    dados = db.get_document("automations_msg_auto") or {}
    dados.setdefault("ativado", False)
    dados.setdefault("mensagens", {})
    return dados

def salvar_config(data: dict) -> None:
    """Salva a configuração na coleção 'msg_auto'."""
    db.save_document("automations_msg_auto", {}, data)

def get_editor_data(msg_id: str) -> dict:
    config = carregar_config()
    return config.get("mensagens", {}).get(msg_id, {}).get("editor_data", {})

def set_editor_data(msg_id: str, editor_data: dict):
    config = carregar_config()
    if msg_id in config.get("mensagens", {}):
        config["mensagens"][msg_id]["editor_data"] = editor_data
        salvar_config(config)
        return True
    return False

def clear_editor_field(msg_id: str, field: str):
    editor_data = get_editor_data(msg_id)
    if field in editor_data:
        del editor_data[field]
        return set_editor_data(msg_id, editor_data)
    return False

def set_editor_field(msg_id: str, field: str, value):
    editor_data = get_editor_data(msg_id)
    editor_data[field] = value
    return set_editor_data(msg_id, editor_data)

def get_message_config(msg_id: str) -> dict:
    config = carregar_config()
    return config.get("mensagens", {}).get(msg_id, {})

def create_new_message(channel_id: str, intervalo: int) -> str:
    config = carregar_config()
    msg_id = str(uuid.uuid4())
    config["mensagens"][msg_id] = {
        "channel_id": channel_id,
        "intervalo_minutos": intervalo,
        "editor_data": {},
        "ultima_enviada": None,
        "last_message_id": None,
    }
    salvar_config(config)
    return msg_id

def delete_message(msg_id: str):
    config = carregar_config()
    if msg_id in config.get("mensagens", {}):
        del config["mensagens"][msg_id]
        salvar_config(config)

def find_button_by_custom_id(custom_id: str):
    config = carregar_config()
    
    for msg_id, msg_data in config.get("mensagens", {}).items():
        editor_data = msg_data.get("editor_data", {})
        for button in editor_data.get("botoes", []):
            button_id = button.get("id")
            
            # O custom_id que vem do Discord é sempre "Anunciar_RuntimeAction_Botao_{button_id}"
            # Então extraímos o button_id do custom_id recebido
            if custom_id.startswith("Anunciar_RuntimeAction_Botao_"):
                button_id_from_custom_id = custom_id.replace("Anunciar_RuntimeAction_Botao_", "")
                if button_id == button_id_from_custom_id:
                    return button
    
    return None