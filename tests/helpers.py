from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from connections.local_db import LocalCollection
import functions.database as database_module
from functions.database import database


@contextmanager
def isolated_database(path: Path):
    previous = database_module.bot_collection
    collection = LocalCollection(path)
    database_module.bot_collection = collection
    database._cache.clear()
    try:
        yield collection
    finally:
        database_module.bot_collection = previous
        database._cache.clear()
