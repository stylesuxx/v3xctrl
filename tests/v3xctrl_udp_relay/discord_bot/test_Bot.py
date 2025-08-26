import asyncio
import io
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from v3xctrl_udp_relay.discord_bot.Bot import Bot
from v3xctrl_udp_relay.discord_bot.RelayClient import RelayClient


class TestBot(unittest.TestCase):
    def setUp(self):
        self.mock_relay_client = MagicMock(spec=RelayClient)
        self.mock_store = MagicMock()

        with patch('v3xctrl_udp_relay.discord_bot.Bot.SessionStore') as mock_session_store_class:
            mock_session_store_class.return_value = self.mock_store
            self.bot = Bot(
                db_path="test.db",
                token="test_token",
                relay_client=self.mock_relay_client,
                command_prefix="!"
            )

    def test_init_with_default_relay_client(self):
        with patch('v3xctrl_udp_relay.discord_bot.Bot.SessionStore') as mock_session_store_class, \
             patch('v3xctrl_udp_relay.discord_bot.Bot.RelayClient') as mock_relay_client_class:

            mock_relay_client_instance = MagicMock()
            mock_relay_client_class.return_value = mock_relay_client_instance

            bot = Bot("test.db", "test_token")

            self.assertEqual(bot.token, "test_token")
            self.assertEqual(bot.relay_client, mock_relay_client_instance)
            mock_relay_client_class.assert_called_once_with()

    def test_init_with_custom_relay_client(self):
        self.assertEqual(self.bot.token, "test_token")
        self.assertEqual(self.bot.relay_client, self.mock_relay_client)
        self.assertEqual(self.bot.store, self.mock_store)

    @patch('discord.ext.commands.Bot.run')
    def test_run_bot(self, mock_super_run):
        self.bot.run_bot()
        mock_super_run.assert_called_once_with("test_token")

    @patch('logging.info')
    def test_on_ready(self, mock_logging_info):
        async def async_test():
            mock_user = MagicMock()
            mock_user.__str__ = MagicMock(return_value="TestBot#1234")

            with patch.object(type(self.bot), 'user', mock_user, create=True):
                await self.bot.on_ready()

            mock_logging_info.assert_called_once_with("Bot connected as TestBot#1234")

        asyncio.run(async_test())

    def test_has_role_with_manage_messages_permission(self):
        mock_member = MagicMock(spec=discord.Member)
        mock_member.guild_permissions.manage_messages = True

        result = self.bot._has_role(mock_member, ['moderator', 'admin'])

        self.assertTrue(result)

    def test_has_role_with_matching_role(self):
        mock_member = MagicMock(spec=discord.Member)
        mock_member.guild_permissions.manage_messages = False

        mock_role1 = MagicMock()
        mock_role1.name = "Moderator"
        mock_role2 = MagicMock()
        mock_role2.name = "Member"

        mock_member.roles = [mock_role1, mock_role2]

        result = self.bot._has_role(mock_member, ['moderator', 'admin'])

        self.assertTrue(result)

    def test_has_role_without_matching_role(self):
        mock_member = MagicMock(spec=discord.Member)
        mock_member.guild_permissions.manage_messages = False

        mock_role = MagicMock()
        mock_role.name = "Member"
        mock_member.roles = [mock_role]

        result = self.bot._has_role(mock_member, ['moderator', 'admin'])

        self.assertFalse(result)

    def test_has_role_case_insensitive(self):
        mock_member = MagicMock(spec=discord.Member)
        mock_member.guild_permissions.manage_messages = False

        mock_role = MagicMock()
        mock_role.name = "MODERATOR"
        mock_member.roles = [mock_role]

        result = self.bot._has_role(mock_member, ['moderator'])

        self.assertTrue(result)

    def test_get_relay_stats(self):
        expected_stats = {"session1": {"created_at": 1234567890}}
        self.mock_relay_client.get_stats.return_value = expected_stats

        result = self.bot._get_relay_stats()

        self.assertEqual(result, expected_stats)
        self.mock_relay_client.get_stats.assert_called_once()

    def test_format_stats_message_empty_stats(self):
        result = self.bot._format_stats_message({})

        self.assertEqual(result, "No active sessions.")

    def test_format_stats_message_with_sessions(self):
        stats = {
            "session1": {
                "created_at": 1234567890,
                "mappings": [
                    {"role": "STREAMER", "address": "192.168.1.100", "port_type": "RTP"},
                    {"role": "VIEWER", "address": "192.168.1.101", "port_type": "RTCP"}
                ]
            }
        }

        result = self.bot._format_stats_message(stats)

        self.assertIn("**Active Sessions: 1**", result)
        self.assertIn("**Session ID:** `session1`", result)
        self.assertIn("<t:1234567890:R>", result)
        self.assertIn("**STREAMER:**", result)
        self.assertIn("192.168.1.100 (RTP)", result)
        self.assertIn("**VIEWER:**", result)
        self.assertIn("192.168.1.101 (RTCP)", result)

    def test_format_stats_message_no_mappings(self):
        stats = {
            "session1": {
                "created_at": 1234567890,
                "mappings": []
            }
        }

        result = self.bot._format_stats_message(stats)

        self.assertIn("*No active mappings*", result)

    def test_handle_stats_command_not_in_guild(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = None

            await self.bot.handle_stats_command(mock_ctx)

            mock_ctx.reply.assert_called_once_with("This command can only be used in a server.")

        asyncio.run(async_test())

    def test_handle_stats_command_author_not_member(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author = MagicMock()  # Not a discord.Member
            mock_ctx.message.add_reaction = AsyncMock()

            await self.bot.handle_stats_command(mock_ctx)

            mock_ctx.message.add_reaction.assert_called_once_with("❌")

        asyncio.run(async_test())

    def test_handle_stats_command_no_permission(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author = MagicMock(spec=discord.Member)
            mock_ctx.message.add_reaction = AsyncMock()

            with patch.object(self.bot, '_has_role', return_value=False):
                await self.bot.handle_stats_command(mock_ctx)

            mock_ctx.message.add_reaction.assert_called_once_with("❌")

        asyncio.run(async_test())

    def test_handle_stats_command_success_short_message(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author = MagicMock(spec=discord.Member)
            mock_ctx.message.add_reaction = AsyncMock()
            mock_ctx.author.send = AsyncMock()

            stats = {"session1": {"created_at": 123, "mappings": []}}

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', return_value=stats), \
                 patch.object(self.bot, '_format_stats_message', return_value="Short message"):

                await self.bot.handle_stats_command(mock_ctx)

            mock_ctx.author.send.assert_called_once_with("Short message")
            mock_ctx.message.add_reaction.assert_called_once_with("✅")

        asyncio.run(async_test())

    def test_handle_stats_command_success_long_message(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author = MagicMock(spec=discord.Member)
            mock_ctx.message.add_reaction = AsyncMock()
            mock_ctx.author.send = AsyncMock()

            stats = {"session1": {"created_at": 123, "mappings": []}}
            long_message = "x" * 2001  # Over 2000 chars

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', return_value=stats), \
                 patch.object(self.bot, '_format_stats_message', return_value=long_message), \
                 patch('discord.File') as mock_file_class, \
                 patch('io.BytesIO') as mock_bytesio:

                mock_file_instance = MagicMock()
                mock_file_class.return_value = mock_file_instance

                await self.bot.handle_stats_command(mock_ctx)

            mock_ctx.author.send.assert_called_once_with(
                "Stats too long for message, sending as file:",
                file=mock_file_instance
            )
            mock_ctx.message.add_reaction.assert_called_once_with("✅")

        asyncio.run(async_test())

    def test_handle_stats_command_dm_forbidden(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author = MagicMock(spec=discord.Member)
            mock_ctx.message.add_reaction = AsyncMock()

            forbidden_exception = discord.Forbidden(
                response=MagicMock(),
                message="DMs disabled"
            )
            mock_ctx.author.send = AsyncMock(side_effect=forbidden_exception)

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', return_value={}), \
                 patch.object(self.bot, '_format_stats_message', return_value="test"):

                await self.bot.handle_stats_command(mock_ctx)

            mock_ctx.reply.assert_called_once_with(
                "I couldn't DM you the stats. Please enable DMs from server members and try again."
            )
            mock_ctx.message.add_reaction.assert_called_once_with("❌")

        asyncio.run(async_test())

    @patch('logging.error')
    def test_handle_stats_command_relay_error(self, mock_logging_error):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author = MagicMock(spec=discord.Member)
            mock_ctx.message.add_reaction = AsyncMock()

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', side_effect=Exception("Relay error")):

                await self.bot.handle_stats_command(mock_ctx)

            mock_ctx.reply.assert_called_once_with(
                "Failed to retrieve relay statistics. Check if the relay server is running."
            )
            mock_ctx.message.add_reaction.assert_called_once_with("❌")
            mock_logging_error.assert_called_once_with("Stats command failed: Relay error")

        asyncio.run(async_test())

    @patch('logging.info')
    def test_handle_requestid_command_guild_context_existing_session(self, mock_logging_info):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")
            mock_ctx.message.add_reaction = AsyncMock()
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = "existing_session"

            await self.bot.handle_requestid_command(mock_ctx)

            mock_ctx.message.add_reaction.assert_called_once_with("✅")
            expected_calls = [
                unittest.mock.call("!requestid called by TestUser#1234 in server, responding via DM."),
                unittest.mock.call("Returning existing session ID for TestUser#1234")
            ]
            mock_logging_info.assert_has_calls(expected_calls)
            mock_ctx.author.send.assert_called_once_with("Your session ID is: `existing_session`")

        asyncio.run(async_test())

    @patch('logging.info')
    def test_handle_requestid_command_dm_context_new_session(self, mock_logging_info):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = None
            mock_ctx.author.id = 67890
            mock_ctx.author.__str__ = MagicMock(return_value="NewUser#5678")
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = None
            self.mock_store.create.return_value = "new_session"

            await self.bot.handle_requestid_command(mock_ctx)

            self.mock_store.create.assert_called_once_with("67890", "NewUser#5678")
            mock_ctx.author.send.assert_called_once_with("Your session ID is: `new_session`")

        asyncio.run(async_test())

    @patch('logging.error')
    def test_handle_requestid_command_create_session_error(self, mock_logging_error):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = None
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")
            mock_ctx.author.send = AsyncMock()

            self.mock_store.get.return_value = None
            self.mock_store.create.side_effect = RuntimeError("Creation failed")

            await self.bot.handle_requestid_command(mock_ctx)

            mock_logging_error.assert_called_once_with(
                "ID generation failed for TestUser#1234: Creation failed"
            )
            mock_ctx.author.send.assert_called_once_with(
                "Failed to generate a unique session ID. Try again later."
            )

        asyncio.run(async_test())

    def test_handle_requestid_command_dm_forbidden(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = None
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")

            forbidden_exception = discord.Forbidden(
                response=MagicMock(),
                message="DMs disabled"
            )
            mock_ctx.author.send = AsyncMock(side_effect=forbidden_exception)

            self.mock_store.get.return_value = "session_id"

            await self.bot.handle_requestid_command(mock_ctx)

            mock_ctx.reply.assert_called_once_with(
                "I couldn't DM you. Please enable DMs from server members and try again."
            )

        asyncio.run(async_test())

    def test_handle_requestid_command_reaction_http_exception(self):
        async def async_test():
            mock_ctx = AsyncMock()
            mock_ctx.guild = MagicMock()
            mock_ctx.author.id = 12345
            mock_ctx.author.__str__ = MagicMock(return_value="TestUser#1234")
            mock_ctx.author.send = AsyncMock()

            http_exception = discord.HTTPException(
                response=MagicMock(),
                message="Failed to add reaction"
            )
            mock_ctx.message.add_reaction = AsyncMock(side_effect=http_exception)

            self.mock_store.get.return_value = "session_id"

            await self.bot.handle_requestid_command(mock_ctx)

            # Should not raise exception, just continue
            mock_ctx.author.send.assert_called_once_with("Your session ID is: `session_id`")

        asyncio.run(async_test())

    def test_stats_command_factory_returns_command(self):
        command = self.bot._stats_command()

        self.assertIsInstance(command, commands.Command)
        self.assertEqual(command.name, "stats")

    def test_requestid_command_factory_returns_command(self):
        command = self.bot._requestid_command()

        self.assertIsInstance(command, commands.Command)
        self.assertEqual(command.name, "requestid")

    def test_stats_command_factory_calls_handler(self):
        async def async_test():
            command = self.bot._stats_command()
            mock_ctx = AsyncMock()

            with patch.object(self.bot, 'handle_stats_command') as mock_handler:
                await command.callback(mock_ctx)
                mock_handler.assert_called_once_with(mock_ctx)

        asyncio.run(async_test())

    def test_requestid_command_factory_calls_handler(self):
        async def async_test():
            command = self.bot._requestid_command()
            mock_ctx = AsyncMock()

            with patch.object(self.bot, 'handle_requestid_command') as mock_handler:
                await command.callback(mock_ctx)
                mock_handler.assert_called_once_with(mock_ctx)

        asyncio.run(async_test())


if __name__ == '__main__':
    unittest.main()
