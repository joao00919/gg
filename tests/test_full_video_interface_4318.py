from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from modules.cloud import reference_interface
from modules.protection.cog import ProtectionCog
from modules.protection.protecaogeral.servidor.cog import ServidorProtectionCog
from tasks.backup.cog import BackupCog
from modules.automations.cog import AutomationModulesCog

ROOT = Path(__file__).resolve().parents[1]


def walk(node):
    yield node
    for child in node.get("components", []) or []:
        yield from walk(child)


def flattened(components):
    nodes = []
    for item in components:
        data = item.to_component_dict()
        nodes.extend(walk(data))
    return nodes


def labels(components):
    return [n["label"] for n in flattened(components) if n.get("label")]


def ids(components):
    return [n["custom_id"] for n in flattened(components) if n.get("custom_id")]


def options(components):
    result = []
    for n in flattened(components):
        for option in n.get("options", []) or []:
            result.append(option.get("label"))
    return result


def fake_inter():
    return SimpleNamespace(guild=None, user=SimpleNamespace(name="Cliente"))


def test_zynex_cloud_matches_oauth_reference_panel():
    bot = SimpleNamespace(user=SimpleNamespace(name="ZYNEX SYSTEM"))
    with patch("modules.cloud.reference_interface.db.get_document", return_value={}):
        components = reference_interface.components(fake_inter(), bot)
    assert labels(components) == [
        "Ativar Sistema",
        "Recuperar Membros",
        "Mensagem OAuth2",
        "Definir canal de Logs",
        "Adicionar Aplicação",
        "Credenciais OAuth2",
        "Desvincular OAuth2",
        "Voltar",
    ]
    assert {
        "Cloud_ToggleSystem",
        "Cloud_RecoverMembers",
        "Cloud_DefinirMensagens",
        "Cloud_DefinirLogs",
        "Cloud_ConfigurarCredenciais",
        "Cloud_UnlinkOAuth",
        "PainelInicial",
    }.issubset(set(ids(components)))
    rendered = json.dumps([c.to_component_dict() for c in components], ensure_ascii=False)
    assert "Autenticação OAuth2" in rendered
    assert "Membros OAuth2" in rendered
    assert "Canal de Logs" in rendered


def test_protection_reference_sections_and_server_controls():
    with patch("modules.protection.cog.db.get_document", return_value={}):
        main = ProtectionCog.PainelComponents(fake_inter())
    assert options(main) == [
        "Proteção Geral",
        "Backup e Restauração",
        "Privatizações",
        "Permissões Internas",
    ]

    with patch("modules.protection.protecaogeral.servidor.cog.db.get_document", return_value={}):
        panel = ServidorProtectionCog(SimpleNamespace()).panel_components()
    assert labels(panel) == [
        "Ativar Proteção de Links",
        "Canal de Logs",
        "Cargos Imunes",
        "Canais Imunes",
        "Voltar",
    ]
    assert options(panel) == [
        "Nenhuma Ação (Apagar Mensagem)",
        "Banir Usuário",
        "Expulsar Usuário",
        "Remover todos os cargos do Usuário",
    ]


def test_backup_reference_buttons_are_connected():
    obj = BackupCog.__new__(BackupCog)
    with (
        patch("tasks.backup.cog.Backup.ListarBackups", return_value=[]),
        patch("tasks.backup.cog.database.obter", return_value={}),
        patch("tasks.backup.cog.database.get_document", return_value={}),
    ):
        panel = obj.get_reference_panel(embed_mode=False)
    assert labels(panel) == [
        "Fazer Backup",
        "Restaurar Servidor",
        "Ativar Sistema",
        "Reiniciar: Desligado",
        "Backup Automático",
        "Voltar",
    ]
    assert {
        "backup_sincronizar", "backup_manage", "backup_system_toggle",
        "backup_restart_toggle", "backup_auto_menu", "Back_To_Protection_Panel",
    }.issubset(set(ids(panel)))


def test_automations_reference_names_and_placeholder():
    with patch("modules.automations.cog.db.get_document", return_value={}):
        panel = AutomationModulesCog.PainelComponents()
    all_options = options(panel)
    for name in (
        "ZYNEX AI Chat",
        "ZYNEX AI Moderator",
        "Contador de Vendas",
        "Limpeza Automática",
        "Auto-Lock",
        "Auto Nuke",
        "Tópicos Automáticos",
        "Sistema de Repostagem",
        "Mensagens Automáticas",
        "Sistema de Sugestões",
        "Monitoramento de Feedbacks",
    ):
        assert name in all_options
    rendered = json.dumps([c.to_component_dict() for c in panel], ensure_ascii=False)
    assert "Selecione uma seção para configurar" in rendered
    assert "Configure e personalize as automações do bot" in rendered


def test_visible_reference_custom_ids_have_listener_cases():
    cloud = (ROOT / "modules/cloud/cog.py").read_text(encoding="utf-8")
    protection = (ROOT / "modules/protection/protecaogeral/servidor/cog.py").read_text(encoding="utf-8")
    backup = (ROOT / "tasks/backup/cog.py").read_text(encoding="utf-8")
    for cid in ("Cloud_ToggleSystem", "Cloud_RecoverMembers", "Cloud_UnlinkOAuth"):
        assert f"case '{cid}'" in cloud
    for cid in ("ProtectionServer_Toggle", "ProtectionServer_Logs", "ProtectionServer_Roles", "ProtectionServer_Channels", "ProtectionServer_Punishment"):
        assert cid in protection
    for cid in ("backup_manage", "backup_system_toggle", "backup_restart_toggle"):
        assert cid in backup

import pytest
from unittest.mock import AsyncMock, MagicMock
from modules.cloud.cog import Cloud


@pytest.mark.asyncio
async def test_cloud_toggle_callback_persists_and_redraws():
    cog = Cloud.__new__(Cloud)
    cog.bot = SimpleNamespace(user=SimpleNamespace(name="ZYNEX"))
    cog.display_cloud_panel = AsyncMock()
    response = SimpleNamespace(is_done=lambda: False, defer=AsyncMock())
    inter = SimpleNamespace(
        component=SimpleNamespace(custom_id="Cloud_ToggleSystem"),
        response=response,
        followup=SimpleNamespace(send=AsyncMock()),
        guild=SimpleNamespace(id=123),
    )
    saved = {}
    with (
        patch("modules.cloud.cog.db.get_document", return_value={"client_id": "bot-oauth", "oauth_enabled": False}),
        patch("modules.cloud.cog.db.save_document", side_effect=lambda key, value: saved.update(value)),
    ):
        await cog.on_button_click(inter)
    assert saved["oauth_enabled"] is True
    assert saved["verification_mode"] == "oauth"
    cog.display_cloud_panel.assert_awaited_once_with(inter)


@pytest.mark.asyncio
async def test_protection_link_toggle_callback_persists_and_redraws():
    cog = ServidorProtectionCog(SimpleNamespace())
    cog.display_panel = AsyncMock()
    inter = SimpleNamespace(component=SimpleNamespace(custom_id="ProtectionServer_Toggle"))
    saved = {}
    with (
        patch("modules.protection.protecaogeral.servidor.cog.db.get_document", return_value={}),
        patch("modules.protection.protecaogeral.servidor.cog.db.save_document", side_effect=lambda key, value: saved.update(value)),
    ):
        await cog.buttons(inter)
    assert saved["links_enabled"] is True
    cog.display_panel.assert_awaited_once_with(inter)


@pytest.mark.asyncio
async def test_backup_system_toggle_callback_persists_and_edits_panel():
    cog = BackupCog.__new__(BackupCog)
    response = SimpleNamespace(defer=AsyncMock())
    inter = SimpleNamespace(
        component=SimpleNamespace(custom_id="backup_system_toggle"),
        response=response,
        edit_original_message=AsyncMock(),
    )
    with (
        patch("tasks.backup.cog.database.get_document", return_value={"mode": "components"}),
        patch("tasks.backup.cog.database.obter", return_value={}),
        patch("tasks.backup.cog.database.salvar") as save,
        patch.object(cog, "get_reference_panel", return_value=[MagicMock()]),
    ):
        await cog.backup_button_listener(inter)
    assert save.call_args.args[1]["backup_system_enabled"] is True
    inter.edit_original_message.assert_awaited_once()

from modules.settings import reference_interface as settings_reference
from modules.automations.ai_chat.cog import AIChatCog


def test_settings_reference_panels_match_video_names():
    with patch("modules.settings.reference_interface.db.get_document", return_value={}):
        moderation = settings_reference.moderation_panel()
        notifications = settings_reference.notifications_panel()
        bot_panel = settings_reference.bot_panel(SimpleNamespace(user=SimpleNamespace(name="ZYNEX")))
        channels = settings_reference.channels_panel()
        roles = settings_reference.roles_panel()
    assert labels(moderation) == ["Adicionar Cargo Ao Entrar", "Editar Boas Vindas", "Voltar"]
    assert labels(notifications) == ["Ligar Notificações", "Definir Chat ID", "Voltar"]
    assert labels(bot_panel) == [
        "Alterar Nome", "Alterar Avatar", "Cor Padrão", "Alterar Status",
        "Alterar Banner", "Alterar Miniatura do Painel", "Voltar",
    ]
    assert "Criar Tudo" in labels(channels)
    assert "Desativar Logs Carrinhos" in labels(channels)
    assert labels(roles) == [
        "Cargo de Cliente", "Cargo de Administrador", "Cargo de Suporte",
        "Criar Cargos Automáticos", "Voltar",
    ]


def test_ai_chat_groq_button_has_direct_modal_handler():
    source = (ROOT / "modules/automations/ai_chat/cog.py").read_text(encoding="utf-8")
    assert 'custom_id="AIChat_ApiKey"' in source
    assert 'if custom_id == "AIChat_ApiKey"' in source
    assert 'send_modal(GroqKeyModal())' in source
    with patch("modules.automations.ai_chat.cog.helpers.carregar_config", return_value={"ativado": True, "chats": {}}), patch("modules.automations.ai_chat.cog.db.get_document", return_value={}):
        panel = AIChatCog.Painel()
    assert "Configurar API Key (Groq)" in labels(panel)


def test_settings_reference_all_visible_controls_have_handlers():
    source = (ROOT / "modules/settings/reference_interface.py").read_text(encoding="utf-8")
    custom_ids = {
        "RefSettings_AutoRole", "RefSettings_Welcome", "RefSettings_TelegramToggle",
        "RefSettings_TelegramChat", "RefSettings_BotName", "RefSettings_BotAvatar",
        "RefSettings_BotColor", "RefSettings_BotStatus", "RefSettings_BotBanner",
        "RefSettings_BotThumbnail", "RefSettings_ChannelChoice",
        "RefSettings_DisableCartLogs", "RefSettings_CreateChannels",
        "RefSettings_RoleClient", "RefSettings_RoleAdmin", "RefSettings_RoleSupport",
        "RefSettings_CreateRoles",
    }
    for cid in custom_ids:
        assert f'custom_id="{cid}"' in source
        assert cid in source[source.find("async def buttons"): ] or cid == "RefSettings_ChannelChoice"


@pytest.mark.asyncio
async def test_settings_dropdown_routes_to_reference_panel():
    from modules.settings.cog import Settings
    reference = SimpleNamespace(show=AsyncMock())
    bot = SimpleNamespace(get_cog=lambda name: reference if name == "SettingsReferenceCog" else None)
    cog = Settings(bot)
    inter = SimpleNamespace(
        component=SimpleNamespace(custom_id="Configuracoes_Select"),
        values=["configurar_bot"],
    )
    await cog.on_dropdown(inter)
    reference.show.assert_awaited_once_with(inter, "configurar_bot")
