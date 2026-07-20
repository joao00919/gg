from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_all_public_commands_have_reference_descriptions():
    source = text("functions/command_policy.py")
    for name in (
        "anunciar", "botconfig", "cleardm", "conectar", "config", "config_painel",
        "configcupom", "criados", "criar", "criar_painel", "criarcupom", "dm",
        "entregar", "estatisticas", "gerarpix", "nuke", "perfil",
        "qrcode_personalizar", "rank", "rankprodutos", "resetar", "set",
        "set_painel", "stockid", "sync_clients",
    ):
        assert f'"{name}":' in source
    assert "_apply_command_descriptions(bot)" in source


def test_ticket_editor_reference_names():
    source = text("modules/tickets/config/edit_panel.py")
    for expected in (
        "PromisseAI", "Editar Opções", "Editar Mensagens", "Horário de Atendimento",
        "Preferências", "Definir Categoria", "Editar Canais", "Editar Cargos",
        "Enviar Painel", "Atualizar Painel", "Deletar Painel", "Deletar Tickets",
    ):
        assert expected in source


def test_opening_panel_is_compact_and_has_reference_buttons():
    source = text("modules/tickets/functions/open_ticket.py")
    assert 'title="Ticket Aberto"' in source
    assert 'label="Painel do Atendente"' in source
    assert 'label="Painel do Usuário"' in source
    assert 'label="Assumir atendimento"' not in source


def test_attendant_panel_reference_actions():
    source = text("modules/tickets/functions/setup_team.py")
    for expected in (
        "Fechar Ticket", "Assumir Ticket", "Notificar Usuário", "Renomear Ticket",
        "Definir Prioridade", "Resolvido", "Arquivar Ticket", "Adicionar Usuário",
        "Remover Usuário", "Transcript", "Histórico", "Gerenciar Call", "Transferir",
    ):
        assert expected in source
    assert "Sair do Atendimento" not in source
    assert '"Pagamento"' not in source


def test_ticket_logs_include_reference_fields():
    source = text("modules/tickets/functions/logs_tickets.py")
    for expected in (
        "Log de Tickets - Abertos", "Log de Tickets - Fechados",
        "Tickets Abertos no Painel", "Data/Hora", "Ver Transcript",
    ):
        assert expected in source
