import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord import app_commands

from v3xctrl_udp_relay.discord_bot.Bot import Bot
from v3xctrl_udp_relay.discord_bot.RelayClient import RelayClient


class TestBot(unittest.TestCase):
    def setUp(self):
        self.mock_relay_client = MagicMock(spec=RelayClient)
        self.mock_store = MagicMock()
        self.test_channel_id = 123456789

        with patch('v3xctrl_udp_relay.discord_bot.Bot.SessionStore') as mock_session_store_class:
            mock_session_store_class.return_value = self.mock_store
            self.bot = Bot(
                db_path="test.db",
                token="test_token",
                channel_id=self.test_channel_id,
                relay_client=self.mock_relay_client
            )

    def test_init_with_default_relay_client(self):
        with patch('v3xctrl_udp_relay.discord_bot.Bot.SessionStore'), \
             patch('v3xctrl_udp_relay.discord_bot.Bot.RelayClient') as mock_relay_client_class:

            mock_relay_client_instance = MagicMock()
            mock_relay_client_class.return_value = mock_relay_client_instance

            bot = Bot("test.db", "test_token", 123456789)

            self.assertEqual(bot.token, "test_token")
            self.assertEqual(bot.relay_client, mock_relay_client_instance)
            self.assertEqual(bot.channel_id, 123456789)
            mock_relay_client_class.assert_called_once_with()

    def test_init_with_custom_relay_client(self):
        self.assertEqual(self.bot.token, "test_token")
        self.assertEqual(self.bot.relay_client, self.mock_relay_client)
        self.assertEqual(self.bot.store, self.mock_store)

    @patch('discord.Client.run')
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

    @patch('logging.info')
    def test_on_message_deletes_user_message_in_designated_channel(self, mock_logging_info):
        async def async_test():
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = MagicMock()
            mock_message.author.__str__ = MagicMock(return_value="User#1234")

            with patch.object(type(self.bot), 'user', MagicMock(), create=True):
                await self.bot.on_message(mock_message)

            mock_message.delete.assert_called_once()
            mock_logging_info.assert_called_once_with(f"Deleted message from {mock_message.author} in channel {self.test_channel_id}")

        asyncio.run(async_test())

    def test_on_message_ignores_bot_own_messages(self):
        async def async_test():
            mock_bot_user = MagicMock()
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = mock_bot_user

            with patch.object(type(self.bot), 'user', mock_bot_user, create=True):
                await self.bot.on_message(mock_message)

            mock_message.delete.assert_not_called()

        asyncio.run(async_test())

    def test_on_message_ignores_messages_in_other_channels(self):
        async def async_test():
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = 999999999  # Different channel
            mock_message.author = MagicMock()

            await self.bot.on_message(mock_message)

            mock_message.delete.assert_not_called()

        asyncio.run(async_test())

    @patch('logging.error')
    def test_on_message_handles_forbidden_error(self, mock_logging_error):
        async def async_test():
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = MagicMock()

            forbidden_exception = discord.Forbidden(
                response=MagicMock(),
                message="Missing Permissions"
            )
            mock_message.delete = AsyncMock(side_effect=forbidden_exception)

            with patch.object(type(self.bot), 'user', MagicMock(), create=True):
                await self.bot.on_message(mock_message)

            mock_logging_error.assert_called_once_with(f"Cannot delete messages in channel {self.test_channel_id} - missing permissions")

        asyncio.run(async_test())

    @patch('logging.error')
    def test_on_message_handles_general_exception(self, mock_logging_error):
        async def async_test():
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = MagicMock()
            mock_message.delete = AsyncMock(side_effect=Exception("Some error"))

            with patch.object(type(self.bot), 'user', MagicMock(), create=True):
                await self.bot.on_message(mock_message)

            mock_logging_error.assert_called_once_with(f"Failed to delete message in channel {self.test_channel_id}: Some error")

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
                    {
                        "role": "STREAMER",
                        "address": "192.168.1.100",
                        "port_type": "RTP",
                        "timeout_in_sec": 60
                    },
                    {
                        "role": "VIEWER",
                        "address": "192.168.1.101",
                        "port_type": "RTCP",
                        "timeout_in_sec": 60
                    }
                ]
            }
        }

        result = self.bot._format_stats_message(stats)

        self.assertIn("**Active Sessions: 1**", result)
        self.assertIn("**Session ID:** `session1`", result)
        self.assertIn("<t:1234567890:R>", result)
        self.assertIn("**STREAMER (Timeout in 60sec):**", result)
        self.assertIn("192.168.1.100 (RTP)", result)
        self.assertIn("**VIEWER (Timeout in 60sec):**", result)
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

    def test_handle_stats_command_wrong_channel(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = 999999999  # Wrong channel
            mock_interaction.response = AsyncMock()

            await self.bot.handle_stats_command(mock_interaction)

            # Should silently ignore - no response sent
            mock_interaction.response.send_message.assert_not_called()
            mock_interaction.response.defer.assert_not_called()

        asyncio.run(async_test())

    def test_handle_stats_command_not_in_guild(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id  # Correct channel
            mock_interaction.guild = None
            mock_interaction.response = AsyncMock()

            await self.bot.handle_stats_command(mock_interaction)

            mock_interaction.response.send_message.assert_called_once_with(
                "This command can only be used in a server.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_handle_stats_command_author_not_member(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = MagicMock()
            mock_interaction.user = MagicMock()  # Not a discord.Member
            mock_interaction.response = AsyncMock()

            await self.bot.handle_stats_command(mock_interaction)

            mock_interaction.response.send_message.assert_called_once_with(
                "This command is only available to server members.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_handle_stats_command_no_permission(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = MagicMock()
            mock_interaction.user = MagicMock(spec=discord.Member)
            mock_interaction.response = AsyncMock()

            with patch.object(self.bot, '_has_role', return_value=False):
                await self.bot.handle_stats_command(mock_interaction)

            mock_interaction.response.send_message.assert_called_once_with(
                "You don't have permission to use this command.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_handle_stats_command_success_short_message(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = MagicMock()
            mock_interaction.user = MagicMock(spec=discord.Member)
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()
            mock_interaction.user.send = AsyncMock()

            stats = {"session1": {"created_at": 123, "mappings": []}}

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', return_value=stats), \
                 patch.object(self.bot, '_format_stats_message', return_value="Short message"):

                await self.bot.handle_stats_command(mock_interaction)

            mock_interaction.user.send.assert_called_once_with("Short message")
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once_with("Stats sent via DM!", ephemeral=True)

        asyncio.run(async_test())

    def test_handle_stats_command_success_long_message(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = MagicMock()
            mock_interaction.user = MagicMock(spec=discord.Member)
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()
            mock_interaction.user.send = AsyncMock()

            stats = {"session1": {"created_at": 123, "mappings": []}}
            long_message = "x" * 2001  # Over 2000 chars

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', return_value=stats), \
                 patch.object(self.bot, '_format_stats_message', return_value=long_message), \
                 patch('discord.File') as mock_file_class, \
                 patch('io.BytesIO'):

                mock_file_instance = MagicMock()
                mock_file_class.return_value = mock_file_instance

                await self.bot.handle_stats_command(mock_interaction)

            mock_interaction.user.send.assert_called_once_with(
                "Stats too long for message, sending as file:",
                file=mock_file_instance
            )
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once_with("Stats sent via DM!", ephemeral=True)

        asyncio.run(async_test())

    def test_handle_stats_command_dm_forbidden(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = MagicMock()
            mock_interaction.user = MagicMock(spec=discord.Member)
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()

            forbidden_exception = discord.Forbidden(
                response=MagicMock(),
                message="DMs disabled"
            )
            mock_interaction.user.send = AsyncMock(side_effect=forbidden_exception)

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', return_value={}), \
                 patch.object(self.bot, '_format_stats_message', return_value="test"):

                await self.bot.handle_stats_command(mock_interaction)

            mock_interaction.followup.send.assert_called_once_with(
                "I couldn't DM you the stats. Please enable DMs from server members and try again.",
                ephemeral=True
            )

        asyncio.run(async_test())

    @patch('logging.error')
    def test_handle_stats_command_relay_error(self, mock_logging_error):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = MagicMock()
            mock_interaction.user = MagicMock(spec=discord.Member)
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()

            with patch.object(self.bot, '_has_role', return_value=True), \
                 patch.object(self.bot, '_get_relay_stats', side_effect=Exception("Relay error")):

                await self.bot.handle_stats_command(mock_interaction)

            mock_interaction.followup.send.assert_called_once_with(
                "Failed to retrieve relay statistics. Check if the relay server is running.",
                ephemeral=True
            )
            mock_logging_error.assert_called_once_with("Stats command failed: Relay error")

        asyncio.run(async_test())

    def test_handle_requestid_command_guild_context_existing_session(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = MagicMock()
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.user.__str__ = MagicMock(return_value="TestUser#1234")
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()
            mock_interaction.user.send = AsyncMock()

            self.mock_store.get.return_value = "existing_session"

            await self.bot.handle_requestid_command(mock_interaction)

            mock_interaction.user.send.assert_called_once_with("Your session ID is: `existing_session`")
            mock_interaction.followup.send.assert_called_once_with("Session ID sent via DM!", ephemeral=True)

        asyncio.run(async_test())

    @patch('logging.info')
    def test_handle_requestid_command_dm_context_new_session(self, mock_logging_info):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = None
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 67890
            mock_interaction.user.__str__ = MagicMock(return_value="NewUser#5678")
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()
            mock_interaction.user.send = AsyncMock()

            self.mock_store.get.return_value = None
            self.mock_store.create.return_value = "new_session"

            await self.bot.handle_requestid_command(mock_interaction)

            self.mock_store.create.assert_called_once_with("67890", "NewUser#5678")
            mock_interaction.user.send.assert_called_once_with("Your session ID is: `new_session`")
            mock_interaction.followup.send.assert_called_once_with("Session ID sent via DM!", ephemeral=True)

        asyncio.run(async_test())

    @patch('logging.error')
    def test_handle_requestid_command_create_session_error(self, mock_logging_error):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = None
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.user.__str__ = MagicMock(return_value="TestUser#1234")
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()

            self.mock_store.get.return_value = None
            self.mock_store.create.side_effect = RuntimeError("Creation failed")

            await self.bot.handle_requestid_command(mock_interaction)

            mock_logging_error.assert_called_once_with(
                "ID generation failed for TestUser#1234: Creation failed"
            )
            mock_interaction.followup.send.assert_called_once_with(
                "Failed to generate a unique session ID. Try again later.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_handle_requestid_command_dm_forbidden(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id
            mock_interaction.guild = None
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.user.__str__ = MagicMock(return_value="TestUser#1234")
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()

            forbidden_exception = discord.Forbidden(
                response=MagicMock(),
                message="DMs disabled"
            )
            mock_interaction.user.send = AsyncMock(side_effect=forbidden_exception)

            self.mock_store.get.return_value = "session_id"

            await self.bot.handle_requestid_command(mock_interaction)

            mock_interaction.followup.send.assert_called_once_with(
                "I couldn't DM you. Please enable DMs from server members and try again.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_stats_command_is_registered(self):
        self.assertIsInstance(self.bot.stats, app_commands.Command)
        self.assertEqual(self.bot.stats.name, "stats")

    def test_requestid_command_is_registered(self):
        self.assertIsInstance(self.bot.requestid, app_commands.Command)
        self.assertEqual(self.bot.requestid.name, "requestid")

    def test_renewid_command_is_registered(self):
        self.assertIsInstance(self.bot.renewid, app_commands.Command)
        self.assertEqual(self.bot.renewid.name, "renewid")

    def test_stats_command_calls_handler(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id

            with patch.object(self.bot, 'handle_stats_command') as mock_handler:
                await self.bot.stats.callback(self.bot, mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction)

        asyncio.run(async_test())

    def test_requestid_command_calls_handler(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id

            with patch.object(self.bot, 'handle_requestid_command') as mock_handler:
                await self.bot.requestid.callback(self.bot, mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction)

        asyncio.run(async_test())

    def test_renewid_command_calls_handler(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id

            with patch.object(self.bot, 'handle_renewid_command') as mock_handler:
                await self.bot.renewid.callback(self.bot, mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction)

        asyncio.run(async_test())


if __name__ == '__main__':
    unittest.main()
