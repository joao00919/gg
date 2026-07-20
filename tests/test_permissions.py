from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from functions.perms import perms


class _GuildPermissions:
    def __init__(self, administrator: bool = False):
        self.administrator = administrator


class _Guild:
    def __init__(self, owner_id: int):
        self.owner_id = owner_id


class _Member:
    def __init__(self, user_id: int, guild: _Guild, administrator: bool = False):
        self.id = user_id
        self.guild = guild
        self.guild_permissions = _GuildPermissions(administrator)


class _Interaction:
    def __init__(self, user_id: int, owner_id: int, administrator: bool = False):
        self.guild = _Guild(owner_id)
        self.user = _Member(user_id, self.guild, administrator)


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_owner_is_authorized(self):
        with patch.dict(os.environ, {"ALLOW_GUILD_ADMIN": "true"}, clear=False):
            self.assertTrue(await perms.check(_Interaction(10, 10)))
            self.assertTrue(await perms.check_owner(_Interaction(10, 10)))

    async def test_server_administrator_is_authorized(self):
        with patch.dict(os.environ, {"ALLOW_GUILD_ADMIN": "true"}, clear=False):
            self.assertTrue(await perms.check(_Interaction(20, 10, administrator=True)))
            self.assertFalse(await perms.check_owner(_Interaction(20, 10, administrator=True)))

    async def test_env_owner_and_admin_are_authorized(self):
        env = {
            "BOT_OWNER_IDS": "30",
            "BOT_ADMIN_IDS": "40",
            "ALLOW_GUILD_ADMIN": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(await perms.check(_Interaction(30, 10)))
            self.assertTrue(await perms.check_owner(_Interaction(30, 10)))
            self.assertTrue(await perms.check(_Interaction(40, 10)))
            self.assertFalse(await perms.check_owner(_Interaction(40, 10)))

    async def test_regular_member_is_denied(self):
        env = {
            "BOT_OWNER_IDS": "",
            "BOT_ADMIN_IDS": "",
            "ALLOW_GUILD_ADMIN": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertFalse(await perms.check(_Interaction(50, 10)))


if __name__ == "__main__":
    unittest.main()
