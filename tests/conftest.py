from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("STORAGE_DRIVER", "local")
os.environ.setdefault("LOCAL_DATABASE_PATH", str(ROOT / "data" / "test_database.json"))
os.environ.setdefault("MAIN_GUILD_ID", "123456789012345678")
os.environ.setdefault("DISCORD_TEST_GUILD_ID", "123456789012345678")
os.environ.setdefault("DISCORD_CLIENT_ID", "123456789012345678")
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("ZYNEX_MIGRATION_BACKUP", "false")
