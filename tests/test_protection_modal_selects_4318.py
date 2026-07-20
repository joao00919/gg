from __future__ import annotations

import ast
from pathlib import Path

import disnake

from modules.protection.protecaogeral.servidor.cog import (
    ImmuneChannelsModal,
    ImmuneRolesModal,
)


class _Cog:
    async def display_panel(self, inter):
        return None


def _select_payload(modal: disnake.ui.Modal) -> dict:
    payload = modal.to_components()
    assert payload, "O modal precisa possuir componentes"
    components = payload.get("components") or []
    assert components, "O modal precisa possuir componentes internos"
    label = components[0]
    component = label.get("component") or {}
    return component


def test_immune_roles_modal_allows_empty_selection():
    component = _select_payload(ImmuneRolesModal(_Cog()))
    assert component["min_values"] == 0
    assert component["max_values"] == 10
    assert component["required"] is False


def test_immune_channels_modal_allows_empty_selection():
    component = _select_payload(ImmuneChannelsModal(_Cog()))
    assert component["min_values"] == 0
    assert component["max_values"] == 10
    assert component["required"] is False


def test_no_optional_modal_select_is_marked_required():
    root = Path(__file__).resolve().parents[1]
    problems: list[str] = []

    for path in root.rglob("*.py"):
        if any(part in {".venv", "venv", "__pycache__"} for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for class_node in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            is_modal = any(
                (isinstance(base, ast.Attribute) and base.attr == "Modal")
                or (isinstance(base, ast.Name) and base.id.endswith("Modal"))
                for base in class_node.bases
            )
            if not is_modal:
                continue

            for call in (n for n in ast.walk(class_node) if isinstance(n, ast.Call)):
                if isinstance(call.func, ast.Attribute):
                    call_name = call.func.attr
                elif isinstance(call.func, ast.Name):
                    call_name = call.func.id
                else:
                    continue
                if not call_name.endswith("Select"):
                    continue

                keywords = {kw.arg: kw.value for kw in call.keywords if kw.arg}
                min_values = keywords.get("min_values")
                required = keywords.get("required")
                optional = isinstance(min_values, ast.Constant) and min_values.value == 0
                explicitly_optional = (
                    isinstance(required, ast.Constant) and required.value is False
                )
                if optional and not explicitly_optional:
                    problems.append(
                        f"{path.relative_to(root)}:{call.lineno} {class_node.name}.{call_name}"
                    )

    assert not problems, "Selects opcionais inválidos em modais:\n" + "\n".join(problems)
