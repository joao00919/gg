from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from modules.tickets.config.config_ticket import PainelTicket_components
from modules.tickets.config.edit_panel import SpecificPanelView_components
from modules.tickets.config.config_opcoes import config_options_components
from modules.tickets.config.edit_message import MessageEditSelectionView_components
from modules.tickets.config.preferencias import PreferenciasView_components
from modules.tickets.config.config_ia import EditIAPromptModal, ConfigIAView_components

ROOT = Path(__file__).resolve().parents[1]


def _component_dicts(items):
    return [item.to_component_dict() for item in items]


def _walk(node):
    yield node
    for child in node.get("components", []) or []:
        yield from _walk(child)


def _nodes(items):
    for root in _component_dicts(items):
        yield from _walk(root)


def _labels(items):
    return [node["label"] for node in _nodes(items) if node.get("label")]


def _placeholders(items):
    return [node["placeholder"] for node in _nodes(items) if node.get("placeholder")]


def _select_labels(items):
    labels = []
    for node in _nodes(items):
        for option in node.get("options", []) or []:
            if option.get("label"):
                labels.append(option["label"])
    return labels


def _store():
    return {
        "tickets_config": {
            "panels": {
                "PANEL": {
                    "id": "PANEL",
                    "name": "Suporte",
                    "enabled": True,
                    "mode": "channel",
                    "ticket_mode": "common",
                    "options": [
                        {
                            "id": "OPT",
                            "name": "Suporte",
                            "description": "Abra um atendimento.",
                            "roles": {"mention": [], "allowed": [], "forbidden": []},
                        }
                    ],
                    "office_hours": {"enabled": False},
                    "preferences": {},
                    "ai_enabled": False,
                    "ai_use_context": False,
                    "ai_prompt": "",
                    "message_style": "embed",
                    "embed": {"title": "Atendimento"},
                    "button": {"label": "Abrir Ticket"},
                    "has_pending_changes": True,
                }
            }
        },
        "custom_colors": {"primary": "#6D28D9"},
    }


def test_ticket_home_matches_video_reference():
    store = _store()
    inter = SimpleNamespace()
    with patch("modules.tickets.config.config_ticket.db.get_document", side_effect=lambda name: store.get(name, {})):
        items = PainelTicket_components(inter)
    assert _labels(items) == ["Desligar Todos", "Criar Painel", "Editar Painel", "Voltar"]
    rendered = json.dumps(_component_dicts(items), ensure_ascii=False)
    assert "Painel > **Gerenciar Tickets**" in rendered
    assert "Painéis configurados" in rendered


def test_ticket_specific_panel_matches_video_reference():
    store = _store()
    bot = SimpleNamespace(get_channel=lambda _id: None)
    inter = SimpleNamespace(bot=bot)
    with patch("modules.tickets.config.edit_panel.db.get_document", side_effect=lambda name: store.get(name, {})):
        items = SpecificPanelView_components(inter, "PANEL")
    assert _labels(items) == [
        "Editar Opções",
        "Editar Mensagens",
        "Modo: Canal",
        "Horário de Atendimento",
        "PromisseAI",
        "Preferências",
        "Definir Categoria",
        "Editar Canais",
        "Editar Cargos",
        "Enviar Painel",
        "Deletar Painel",
        "Deletar Tickets",
        "Voltar",
    ]
    rendered = json.dumps(_component_dicts(items), ensure_ascii=False)
    for value in ("Status e Configurações", "Modo de Atendimento", "PromisseAI"):
        assert value in rendered


def test_ticket_options_manager_matches_video_reference():
    store = _store()
    inter = SimpleNamespace()
    with patch("modules.tickets.config.config_opcoes.db.get_document", side_effect=lambda name: store.get(name, {})):
        items = config_options_components(inter, "PANEL")
    assert _labels(items) == ["Adicionar Opção", "Voltar"]
    placeholders = _placeholders(items)
    assert "Selecione uma opção para editar..." in placeholders
    assert "Selecione uma ou mais opções para remover..." in placeholders
    rendered = json.dumps(_component_dicts(items), ensure_ascii=False)
    assert "Você tem **1/25** opções" in rendered


def test_ticket_message_editor_has_all_video_actions():
    store = _store()
    inter = SimpleNamespace()
    with patch("modules.tickets.config.edit_message.db.get_document", side_effect=lambda name: store.get(name, {})):
        items = MessageEditSelectionView_components(inter, "PANEL")
    assert _select_labels(items) == [
        "Editar Mensagem do Painel",
        "Editar Mensagem de Abertura",
        "Editar Mensagem de Fechamento",
        "Editar Mensagem de Notificar",
        "Editar Mensagem de Adicionar Usuário",
        "Editar Mensagem de Remover Usuário",
        "Editar Mensagem de Assumir Ticket",
        "Editar Mensagem de Transferir",
        "Editar Mensagem de Criar Call",
        "Editar Mensagem de Transcript",
    ]


def test_ticket_preferences_matches_video_reference():
    store = _store()
    inter = SimpleNamespace()
    with patch("modules.tickets.config.preferencias.db.get_document", side_effect=lambda name: store.get(name, {})):
        items = PreferenciasView_components(inter, "PANEL")
    assert _select_labels(items) == [
        "Configurar Sistema de Transcripts",
        "Configurar Setup Membro",
        "Configurar Setup Atendente",
        "Configurar Fechamento de Tickets",
        "Configurar Formulários",
    ]


def test_ticket_ai_panel_is_rebranded_and_complete():
    store = _store()
    inter = SimpleNamespace()
    with patch("modules.tickets.config.config_ia.db.get_document", side_effect=lambda name: store.get(name, {})):
        items = ConfigIAView_components(inter, "PANEL")
        modal = EditIAPromptModal("PANEL")
    rendered = json.dumps(_component_dicts(items), ensure_ascii=False)
    assert "PromisseAI" in rendered
    assert modal.title == "Editar Instruções da PromisseAI"
    modal_dict = modal.to_components()
    serialized = json.dumps(modal_dict, ensure_ascii=False)
    assert "Instruções Adicionais para a IA" in serialized
    assert "Usar Contexto (Sim/Não)" in serialized


def test_ticket_unknown_actions_have_visible_fallback():
    source = (ROOT / "modules/tickets/config/cog.py").read_text(encoding="utf-8")
    assert "Ação de ticket não reconhecida ou indisponível" in source
    assert "Seleção de ticket não reconhecida ou indisponível" in source
    assert "from functions.interaction_runtime import respond_panel, respond_error" in source
