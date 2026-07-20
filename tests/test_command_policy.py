from __future__ import annotations

import unittest

import disnake
from disnake.ext import commands

from functions.command_policy import REQUIRED_SLASH_COMMANDS, enforce_command_policy


class CommandPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_registry_contains_exact_requested_commands(self):
        intents = disnake.Intents.none()
        bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, test_guilds=[123456789012345678])
        try:
            bot.load_extension("modules")
            bot.load_extension("commands")
            report = enforce_command_policy(bot)
            self.assertEqual(set(report["active"]), set(REQUIRED_SLASH_COMMANDS))
            self.assertNotIn("carteira", report["active"])
            self.assertEqual(len(report["active"]), 25)
        finally:
            await bot.close()
