from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import disnake
import pytest

from functions.discord_runtime_safety import (
    install_listener_error_fallback,
    install_modal_payload_safety,
)


def _nested_component(payload: dict) -> dict:
    return payload["components"][0]["component"]


def test_optional_role_select_modal_is_serialized_as_not_required():
    install_modal_payload_safety()
    modal = disnake.ui.Modal(
        title="Cargos imunes",
        custom_id="test_roles",
        components=[
            disnake.ui.Label(
                "Cargos",
                disnake.ui.RoleSelect(
                    custom_id="roles",
                    min_values=0,
                    max_values=5,
                ),
            )
        ],
    )
    component = _nested_component(modal.to_components())
    assert component["type"] == 6
    assert component["min_values"] == 0
    assert component["required"] is False


def test_required_role_select_with_minimum_one_is_preserved():
    install_modal_payload_safety()
    modal = disnake.ui.Modal(
        title="Cargo obrigatório",
        custom_id="test_required_role",
        components=[
            disnake.ui.Label(
                "Cargo",
                disnake.ui.RoleSelect(
                    custom_id="role",
                    min_values=1,
                    max_values=1,
                    required=True,
                ),
            )
        ],
    )
    component = _nested_component(modal.to_components())
    assert component["min_values"] == 1
    assert component["required"] is True


def test_modal_patch_is_idempotent():
    first = install_modal_payload_safety()
    second = install_modal_payload_safety()
    # O patch pode já ter sido instalado por outro teste, mas nunca deve duplicar.
    assert second is False
    assert first in {True, False}


@pytest.mark.asyncio
async def test_listener_error_fallback_responds_to_interaction():
    bot = SimpleNamespace()
    install_listener_error_fallback(bot)
    inter = SimpleNamespace(spec=disnake.Interaction)
    # isinstance precisa reconhecer uma Interaction real; use um mock com spec não basta.
    # Testamos o handler com um objeto mínimo herdando da classe sem inicialização.
    real_inter = object.__new__(disnake.Interaction)
    with patch(
        "functions.discord_runtime_safety.respond_error",
        new=AsyncMock(),
    ) as responder:
        try:
            raise RuntimeError("falha de teste")
        except RuntimeError:
            await bot.on_error("on_button_click", real_inter)
    responder.assert_awaited_once()
    assert bot._zynex_listener_error_fallback is True
