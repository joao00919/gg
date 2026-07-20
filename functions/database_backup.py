from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any

from connections.mongo_db import collection as bot_collection

_LOCK = threading.Lock()
_SENSITIVE = re.compile(r"token|secret|password|api[_-]?key|authorization|credential", re.I)


def _sanitize(value: Any, key: str = "") -> Any:
    if _SENSITIVE.search(key):
        return "***REMOVIDO***"
    if isinstance(value, dict):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items() if str(k) != "_id"}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def create_database_backup(*, reason: str = "manual", backup_dir: str | None = None, rotation: int | None = None) -> dict:
    """Exporta os documentos sem segredos e grava checksum SHA-256."""
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError("Já existe um backup em execução.")
    try:
        root = Path(backup_dir or os.getenv("ZYNEX_BACKUP_DIR", "backups")).resolve()
        root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        documents = {}
        for document in bot_collection.find({}):
            document_id = str(document.get("_id", "unknown"))
            documents[document_id] = _sanitize(document)
        payload = {
            "format": 1,
            "application": "ZYNEX Systems",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "documents": documents,
        }
        raw = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        path = root / f"zynex-backup-{timestamp}.json"
        temp = path.with_suffix(".tmp")
        temp.write_bytes(raw)
        temp.replace(path)
        path.with_suffix(".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
        keep = max(1, int(rotation or os.getenv("ZYNEX_BACKUP_ROTATION", "10")))
        backups = sorted(root.glob("zynex-backup-*.json"), reverse=True)
        for old in backups[keep:]:
            old.unlink(missing_ok=True)
            old.with_suffix(".sha256").unlink(missing_ok=True)
        return {"path": str(path), "sha256": digest, "documents": len(documents), "createdAt": payload["createdAt"]}
    finally:
        _LOCK.release()


def validate_database_backup(path: str | os.PathLike[str]) -> dict:
    file_path = Path(path).resolve()
    raw = file_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if data.get("format") != 1 or not isinstance(data.get("documents"), dict):
        raise ValueError("Formato de backup inválido.")
    digest = hashlib.sha256(raw).hexdigest()
    checksum_path = file_path.with_suffix(".sha256")
    if checksum_path.exists():
        expected = checksum_path.read_text(encoding="utf-8").strip().split(maxsplit=1)[0]
        if expected and expected.lower() != digest.lower():
            raise ValueError("Checksum do backup inválido.")
    return {"ok": True, "sha256": digest, "documents": len(data["documents"])}


def _merge_sanitized_backup(current: Any, restored: Any) -> Any:
    """Preserva segredos atuais quando o backup contém o marcador sanitizado."""
    if restored == "***REMOVIDO***":
        return current
    if isinstance(restored, dict):
        current_dict = current if isinstance(current, dict) else {}
        merged = dict(current_dict)
        for key, value in restored.items():
            existing = current_dict.get(key)
            if value == "***REMOVIDO***" and key not in current_dict:
                continue
            merged[key] = _merge_sanitized_backup(existing, value)
        return merged
    if isinstance(restored, list):
        # Listas são tratadas como unidade; um marcador interno exige manter a lista atual.
        if any(item == "***REMOVIDO***" for item in restored):
            return current if current is not None else []
        return [_merge_sanitized_backup(None, item) for item in restored]
    return restored


def restore_database_backup(path: str | os.PathLike[str], *, confirmation: str) -> dict:
    if confirmation != "RESTAURAR":
        raise ValueError("Confirmação inválida. Use RESTAURAR.")
    file_path = Path(path).resolve()
    validation = validate_database_backup(file_path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    safety = create_database_backup(reason="pre_restore")
    restored = 0
    for document_id, document in data["documents"].items():
        current = bot_collection.find_one({"_id": document_id}) or {}
        payload = _merge_sanitized_backup(current, dict(document))
        payload["_id"] = document_id
        bot_collection.replace_one({"_id": document_id}, payload, upsert=True)
        restored += 1
    try:
        from functions.database import database as database_facade
        with database_facade._cache_lock:
            database_facade._cache.clear()
    except Exception:
        pass
    return {"restored": restored, "source": str(file_path), "safetyBackup": safety, "validation": validation}
