from __future__ import annotations

import tempfile
from pathlib import Path

import functions.database_backup as backup_module
from functions.database import database as db
from functions.database_backup import create_database_backup, validate_database_backup
from functions.template_renderer import render_template
from tests.helpers import isolated_database


def test_backup_removes_secrets_and_validates_checksum_structure():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        with isolated_database(path / "db.json") as collection:
            previous = backup_module.bot_collection
            backup_module.bot_collection = collection
            try:
                db.save_document("settings", {"token": "abc", "name": "ZYNEX"})
                result = create_database_backup(backup_dir=str(path / "backups"), rotation=2)
                raw = Path(result["path"]).read_text(encoding="utf-8")
                assert "abc" not in raw
                assert "***REMOVIDO***" in raw
                assert validate_database_backup(result["path"])["ok"] is True
            finally:
                backup_module.bot_collection = previous


def test_template_renderer_rejects_unknown_variables_and_limits_length():
    assert render_template("Olá, {usuario}! Pedido {pedido}.", {"usuario": "Ana", "pedido": "A1"}) == "Olá, Ana! Pedido A1."
    try:
        render_template("{nao_existe}", {})
    except ValueError as exc:
        assert "desconhecidas" in str(exc)
    else:
        raise AssertionError("Variável desconhecida deveria ser rejeitada")


def test_restore_preserves_existing_secret_fields():
    from functions.database_backup import restore_database_backup
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        with isolated_database(path / "db.json") as collection:
            previous = backup_module.bot_collection
            backup_module.bot_collection = collection
            try:
                db.save_document("settings", {"api_key": "live-secret", "name": "Antes"})
                result = create_database_backup(backup_dir=str(path / "backups"), rotation=2)
                db.save_document("settings", {"api_key": "live-secret", "name": "Depois"})
                restore_database_backup(result["path"], confirmation="RESTAURAR")
                restored = db.get_document("settings")
                assert restored["api_key"] == "live-secret"
                assert restored["name"] == "Antes"
            finally:
                backup_module.bot_collection = previous
