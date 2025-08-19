import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

import discord
from discord.ext import commands

from v3xctrl_udp_relay.discord_bot import Bot


class TestBot(unittest.TestCase):
    @patch('v3xctrl_udp_relay.discord_bot.Bot.SessionStore')
    def setUp(self, mock_session_store_class):
        self.db_path = "test.db"
        self.token = "test_token"
        self.command_prefix = "!"

        self.mock_store = MagicMock()
        mock_session_store_class.return_value = self.mock_store

        # Create bot with real initialization to ensure line 31 is hit
        with patch('discord.ext.commands.Bot.__init__', return_value=None), \
             patch.object(Bot, 'add_command') as mock_add_command:
            self.bot = Bot(self.db_path, self.token, self.command_prefix)

        # Verify the super().__init__ and add_command were called
        mock_add_command.assert_called_once()

    def test_initialization_line_31_coverage(self):
        # This test specifically ensures line 31 (super().__init__) is covered
        with patch('v3xctrl_udp_relay.discord_bot.Bot.SessionStore') as mock_session_store, \
             patch('discord.ext.commands.Bot.__init__') as mock_super_init, \
             patch.object(Bot, 'add_command'):

            bot = Bot(self.db_path, self.token, self.command_prefix)

            # Verify super().__init__ was called - check that it was called with the right types
            mock_super_init.assert_called_once()
            call_args = mock_super_init.call_args
            self.assertEqual(call_args[1]['command_prefix'], self.command_prefix)
            self.assertIsInstance(call_args[1]['intents'], discord.Intents)
            self.assertTrue(call_args[1]['intents'].message_content)

    @patch('v3xctrl_udp_relay.discord_bot.Bot.commands.Bot.run')
    def test_run_bot(self, mock_super_run):
        self.bot.run_bot()
        mock_super_run.assert_called_once_with(self.token)

    @patch('logging.info')
    def test_on_ready(self, mock_logging_info):
        async def async_test():
            # Mock the user property correctly
            mock_user = MagicMock()
            mock_user.__str__ = MagicMock(return_value="TestBot#1234")

            with patch.object(type(self.bot), 'user', mock_user, create=True):
                await self.bot.on_ready()

            mock_logging_info.assert_called_once_with("Bot connected as TestBot#1234")

        asyncio.run(async_test())

    @patch('logging.info')
    def test_requestid_command_guild_existing_session(self, mock_logging_info):
        async def async_test():
            # Test lines 36-46: guild context with existing session
            mock_ctx = AsyncMock()
            mock_ctx.bot = self.bot
            mock_ctx.guild = MagicMock()  # Not None - triggers guild branch
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")
            mock_ctx.message.add_reaction = AsyncMock()
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = "existing_session_id"

            command_func = self.bot._requestid_command()
            await command_func(mock_ctx)

            # Verify guild-specific behavior (lines 38-43)
            mock_ctx.message.add_reaction.assert_called_once_with("✅")

            # Verify logging calls (lines 43, 51)
            expected_calls = [
                call("!requestid called by TestUser#1234 in server, responding via DM."),
                call("Returning existing session ID for TestUser#1234")
            ]
            mock_logging_info.assert_has_calls(expected_calls)

            # Verify session handling (lines 47-52)
            self.mock_store.get.assert_called_once_with("12345")
            mock_ctx.author.send.assert_called_once_with("Your session ID is: `existing_session_id`")

        asyncio.run(async_test())

    @patch('logging.info')
    def test_requestid_command_guild_reaction_fails(self, mock_logging_info):
        async def async_test():
            # Test line 40-42: HTTPException handling
            mock_ctx = AsyncMock()
            mock_ctx.bot = self.bot
            mock_ctx.guild = MagicMock()
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")

            # Create proper HTTPException with required arguments
            http_exception = discord.HTTPException(
                response=MagicMock(),
                message="Failed to add reaction"
            )
            mock_ctx.message.add_reaction = AsyncMock(side_effect=http_exception)
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = "session_id"

            command_func = self.bot._requestid_command()
            await command_func(mock_ctx)

            # The exception should be caught and passed (lines 40-42)
            mock_ctx.message.add_reaction.assert_called_once_with("✅")
            mock_logging_info.assert_called()

        asyncio.run(async_test())

    @patch('logging.info')
    @patch('logging.error')
    def test_requestid_command_create_new_session(self, mock_logging_error, mock_logging_info):
        async def async_test():
            # Test lines 53-57: new session creation
            mock_ctx = AsyncMock()
            mock_ctx.bot = self.bot
            mock_ctx.guild = None  # DM context
            mock_ctx.author.id = 67890
            mock_ctx.author.__str__ = MagicMock(return_value="NewUser#5678")
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = None  # No existing session
            self.mock_store.create.return_value = "new_session_id"

            command_func = self.bot._requestid_command()
            await command_func(mock_ctx)

            # Verify new session creation path (lines 53-57)
            self.mock_store.get.assert_called_once_with("67890")
            self.mock_store.create.assert_called_once_with("67890", "NewUser#5678")
            mock_ctx.author.send.assert_called_once_with("Your session ID is: `new_session_id`")

        asyncio.run(async_test())

    @patch('logging.error')
    def test_requestid_command_create_session_fails(self, mock_logging_error):
        async def async_test():
            # Test lines 55-59: RuntimeError handling
            mock_ctx = AsyncMock()
            mock_ctx.bot = self.bot
            mock_ctx.guild = None
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = None
            self.mock_store.create.side_effect = RuntimeError("ID generation failed")

            command_func = self.bot._requestid_command()
            await command_func(mock_ctx)

            # Verify error handling (lines 56-59)
            mock_logging_error.assert_called_once_with("ID generation failed for TestUser#1234: ID generation failed")
            mock_ctx.author.send.assert_called_once_with("Failed to generate a unique session ID. Try again later.")

        asyncio.run(async_test())

    def test_requestid_command_dm_forbidden(self):
        async def async_test():
            # Test lines 61-62: Forbidden exception handling
            mock_ctx = AsyncMock()
            mock_ctx.bot = self.bot
            mock_ctx.guild = None
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")

            # Create proper Forbidden exception with required arguments
            forbidden_exception = discord.Forbidden(
                response=MagicMock(),
                message="DMs disabled"
            )
            mock_ctx.author.send = AsyncMock(side_effect=forbidden_exception)
            mock_ctx.reply = AsyncMock()

            self.mock_store.get.return_value = "session_id"

            command_func = self.bot._requestid_command()
            await command_func(mock_ctx)

            # Verify Forbidden exception handling (lines 61-62)
            mock_ctx.author.send.assert_called_once_with("Your session ID is: `session_id`")
            mock_ctx.reply.assert_called_once_with("I couldn't DM you. Please enable DMs from server members and try again.")

        asyncio.run(async_test())

    def test_requestid_command_dm_context_no_reaction(self):
        async def async_test():
            # Test line 37: ctx.guild is None branch
            mock_ctx = AsyncMock()
            mock_ctx.bot = self.bot
            mock_ctx.guild = None  # This should skip the guild-specific code
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = "dm_session_id"

            command_func = self.bot._requestid_command()
            await command_func(mock_ctx)

            # In DM context, no reaction should be attempted
            mock_ctx.author.send.assert_called_once_with("Your session ID is: `dm_session_id`")

        asyncio.run(async_test())

    def test_requestid_command_returns_command_object(self):
        # Test that _requestid_command returns a Command object
        command_obj = self.bot._requestid_command()

        self.assertIsNotNone(command_obj)
        # The returned object is a discord Command, check its name
        self.assertEqual(command_obj.name, "requestid")
        self.assertTrue(callable(command_obj))


if __name__ == '__main__':
    unittest.main()
