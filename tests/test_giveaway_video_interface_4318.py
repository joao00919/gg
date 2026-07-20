from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.giveaways import cog as giveaway_cog
from modules.giveaways import config_giveaways


ROOT = Path(__file__).resolve().parents[1]


def test_video_giveaway_labels_and_ids_are_present():
    source = (ROOT / "modules/giveaways/config_giveaways.py").read_text(encoding="utf-8")
    expected = [
        "Modo Real",
        "Modo Fake",
        "Alterar Nome",
        "Configurar Prêmio",
        "Requisitos",
        "Cargos Bônus",
        "Customizar Mensagem",
        "Configurar Envio",
        "Excluir Sorteio",
        "GiveawayEdit_Rename_",
        "GiveawayEdit_Prize_",
        "GiveawayEdit_Requirements_",
        "GiveawayEdit_BonusRoles_",
        "GiveawayEdit_ConfigSend_",
    ]
    for text in expected:
        assert text in source


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "view_name"),
    [
        ("Prize", "PrizeView_components"),
        ("Requirements", "RequirementsView_components"),
        ("BonusRoles", "BonusRolesView_components"),
        ("ConfigSend", "ManageTasksView_components"),
    ],
)
async def test_video_giveaway_buttons_open_their_functional_panels(monkeypatch, action, view_name):
    monkeypatch.setattr(giveaway_cog.db, "get_document", lambda _name: {"mode": "components"})
    marker = [object()]
    monkeypatch.setattr(giveaway_cog, view_name, lambda *_args, **_kwargs: marker)

    panel = giveaway_cog.Giveaways(bot=None)

    async def no_wait(_inter):
        return None

    panel._mode_aware_wait = no_wait

    class FakeInteraction:
        def __init__(self):
            self.edited = None

        async def edit_original_message(self, **kwargs):
            self.edited = kwargs

    inter = FakeInteraction()
    await panel.handle_giveaway_edit_actions(inter, action, "abc123")
    assert inter.edited == {"components": marker}


@pytest.mark.asyncio
async def test_video_giveaway_rename_opens_modal_without_defer(monkeypatch):
    monkeypatch.setattr(giveaway_cog.db, "get_document", lambda _name: {"mode": "components"})
    monkeypatch.setattr(
        giveaway_cog.db,
        "obter",
        lambda _path: {"abc123": {"name": "Sorteio Atual"}},
    )

    panel = giveaway_cog.Giveaways(bot=None)

    class FakeResponse:
        def __init__(self):
            self.modal = None

        async def send_modal(self, modal):
            self.modal = modal

    inter = SimpleNamespace(response=FakeResponse())
    await panel.handle_giveaway_edit_actions(inter, "Rename", "abc123")
    assert isinstance(inter.response.modal, config_giveaways.RenameGiveawayModal)
