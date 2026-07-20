"""Persistência documental local compatível com o subconjunto usado pelo bot.

Este módulo permite executar o projeto sem MongoDB durante desenvolvimento e testes.
Os dados são gravados em JSON com escrita atômica e proteção por lock.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class InsertOneResult:
    inserted_id: Any


@dataclass(slots=True)
class DeleteResult:
    deleted_count: int


@dataclass(slots=True)
class UpdateResult:
    matched_count: int
    modified_count: int
    upserted_id: Any = None


def _get_nested(document: dict[str, Any], dotted_key: str) -> tuple[bool, Any]:
    current: Any = document
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _matches_condition(exists: bool, value: Any, condition: Any) -> bool:
    if not isinstance(condition, dict) or not any(str(k).startswith("$") for k in condition):
        return exists and value == condition

    for operator, expected in condition.items():
        if operator == "$exists":
            if exists is not bool(expected):
                return False
        elif operator == "$eq":
            if not exists or value != expected:
                return False
        elif operator == "$ne":
            if exists and value == expected:
                return False
        elif operator == "$in":
            if not exists or value not in expected:
                return False
        elif operator == "$nin":
            if exists and value in expected:
                return False
        elif operator == "$gt":
            if not exists or not (value > expected):
                return False
        elif operator == "$gte":
            if not exists or not (value >= expected):
                return False
        elif operator == "$lt":
            if not exists or not (value < expected):
                return False
        elif operator == "$lte":
            if not exists or not (value <= expected):
                return False
        else:
            raise ValueError(f"Operador de consulta local não suportado: {operator}")
    return True


def _matches(document: dict[str, Any], query: dict[str, Any] | None) -> bool:
    if not query:
        return True

    for key, condition in query.items():
        if key == "$and":
            if not all(_matches(document, item) for item in condition):
                return False
            continue
        if key == "$or":
            if not any(_matches(document, item) for item in condition):
                return False
            continue
        if key == "$nor":
            if any(_matches(document, item) for item in condition):
                return False
            continue

        exists, value = _get_nested(document, key)
        if not _matches_condition(exists, value, condition):
            return False
    return True


def _apply_projection(document: dict[str, Any], projection: dict[str, int] | None) -> dict[str, Any]:
    if not projection:
        return copy.deepcopy(document)

    included = {key for key, enabled in projection.items() if enabled}
    excluded = {key for key, enabled in projection.items() if not enabled}

    if included:
        result: dict[str, Any] = {}
        for key in included:
            exists, value = _get_nested(document, key)
            if exists:
                result[key] = copy.deepcopy(value)
        if projection.get("_id", 1) and "_id" in document:
            result.setdefault("_id", copy.deepcopy(document["_id"]))
        return result

    result = copy.deepcopy(document)
    for key in excluded:
        result.pop(key, None)
    return result


class LocalCollection:
    """Coleção local com API semelhante ao PyMongo usada pelo projeto."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                raw = {}

            if isinstance(raw, dict) and "documents" in raw:
                raw = raw.get("documents", {})
            if not isinstance(raw, dict):
                raise RuntimeError(f"Banco local inválido: {self.path}")
            return raw

    def _write(self, documents: dict[str, dict[str, Any]]) -> None:
        payload = {"format": 1, "documents": documents}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, self.path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)

    @staticmethod
    def _key(document_id: Any) -> str:
        if document_id is None:
            raise ValueError("Todo documento local precisa de um campo '_id'.")
        return str(document_id)

    def find_one(
        self,
        query: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        for document in self.find(query, projection):
            return document
        return None

    def find(
        self,
        query: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        documents = self._read()
        return [
            _apply_projection(document, projection)
            for document in documents.values()
            if _matches(document, query)
        ]

    def count_documents(self, query: dict[str, Any] | None = None) -> int:
        return len(self.find(query))

    def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        document_copy = copy.deepcopy(document)
        key = self._key(document_copy.get("_id"))
        with self._lock:
            documents = self._read()
            if key in documents:
                raise ValueError(f"Documento duplicado no banco local: _id={key}")
            documents[key] = document_copy
            self._write(documents)
        return InsertOneResult(inserted_id=document_copy["_id"])

    def replace_one(
        self,
        query: dict[str, Any],
        replacement: dict[str, Any],
        upsert: bool = False,
    ) -> UpdateResult:
        replacement_copy = copy.deepcopy(replacement)
        with self._lock:
            documents = self._read()
            matched_key = next(
                (key for key, document in documents.items() if _matches(document, query)),
                None,
            )
            if matched_key is not None:
                replacement_copy.setdefault("_id", documents[matched_key].get("_id"))
                new_key = self._key(replacement_copy.get("_id"))
                documents.pop(matched_key, None)
                documents[new_key] = replacement_copy
                self._write(documents)
                return UpdateResult(matched_count=1, modified_count=1)

            if not upsert:
                return UpdateResult(matched_count=0, modified_count=0)

            if "_id" not in replacement_copy and isinstance(query.get("_id"), (str, int)):
                replacement_copy["_id"] = query["_id"]
            key = self._key(replacement_copy.get("_id"))
            documents[key] = replacement_copy
            self._write(documents)
            return UpdateResult(matched_count=0, modified_count=0, upserted_id=replacement_copy["_id"])

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> UpdateResult:
        with self._lock:
            documents = self._read()
            matched_key = next(
                (key for key, document in documents.items() if _matches(document, query)),
                None,
            )
            if matched_key is None:
                if not upsert:
                    return UpdateResult(0, 0)
                base = {k: v for k, v in query.items() if not k.startswith("$") and not isinstance(v, dict)}
                base.setdefault("_id", query.get("_id"))
                if base.get("_id") is None:
                    raise ValueError("Upsert local exige um '_id'.")
                documents[self._key(base["_id"])] = base
                matched_key = self._key(base["_id"])
                upserted_id = base["_id"]
            else:
                upserted_id = None

            document = documents[matched_key]
            if any(str(key).startswith("$") for key in update):
                for key, value in update.get("$set", {}).items():
                    document[key] = copy.deepcopy(value)
                for key in update.get("$unset", {}):
                    document.pop(key, None)
                for key, value in update.get("$inc", {}).items():
                    document[key] = document.get(key, 0) + value
            else:
                document = copy.deepcopy(update)
                document.setdefault("_id", documents[matched_key].get("_id"))

            new_key = self._key(document.get("_id"))
            documents.pop(matched_key, None)
            documents[new_key] = document
            self._write(documents)
            return UpdateResult(1 if upserted_id is None else 0, 1, upserted_id)

    def delete_one(self, query: dict[str, Any]) -> DeleteResult:
        with self._lock:
            documents = self._read()
            key = next((key for key, document in documents.items() if _matches(document, query)), None)
            if key is None:
                return DeleteResult(0)
            documents.pop(key, None)
            self._write(documents)
            return DeleteResult(1)

    def delete_many(self, query: dict[str, Any]) -> DeleteResult:
        with self._lock:
            documents = self._read()
            keys = [key for key, document in documents.items() if _matches(document, query)]
            for key in keys:
                documents.pop(key, None)
            if keys:
                self._write(documents)
            return DeleteResult(len(keys))

    def create_index(self, *_args: Any, **_kwargs: Any) -> str:
        return "local_noop_index"

    def ping(self) -> bool:
        self._read()
        return True
