from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_application_has_no_empty_function_bodies():
    empty = []
    for path in ROOT.rglob("*.py"):
        if any(part in {"tests", "__pycache__", ".venv", "venv"} for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = [
                item for item in node.body
                if not (
                    isinstance(item, ast.Expr)
                    and isinstance(item.value, ast.Constant)
                    and isinstance(item.value.value, str)
                )
            ]
            if not body or all(isinstance(item, ast.Pass) for item in body):
                empty.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}")
    assert not empty, "Funções vazias encontradas: " + ", ".join(empty)


def test_no_prozynexal_implementation_markers_or_real_env_file():
    import re
    prozynexal_comment = re.compile(r"^\s*#\s*(?:TODO|FIXME)\b", re.IGNORECASE | re.MULTILINE)
    markers = ("NotImplementedError", "ainda não implementada", "Placeholder for future")
    hits = []
    for path in ROOT.rglob("*.py"):
        if any(part in {"tests", "__pycache__", ".venv", "venv"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if prozynexal_comment.search(text):
            hits.append(f"{path.relative_to(ROOT)}:TODO/FIXME")
        for marker in markers:
            if marker.lower() in text.lower():
                hits.append(f"{path.relative_to(ROOT)}:{marker}")
    assert not hits, "Marcadores provisórios encontrados: " + ", ".join(hits)
    assert not (ROOT / ".env").exists()
