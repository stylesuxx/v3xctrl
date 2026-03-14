import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord import app_commands

from v3xctrl_relay.discord_bot.Bot import Bot


class TestBot(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.test_channel_id = 123456789

        with patch("v3xctrl_relay.discord_bot.Bot.SessionStore") as mock_session_store_class:
            mock_session_store_class.return_value = self.mock_store
            self.bot = Bot(
                db_path="test.db",
                token="test_token",
                channel_id=self.test_channel_id,
            )

    def test_init(self):
        self.assertEqual(self.bot.token, "test_token")
        self.assertEqual(self.bot.store, self.mock_store)
        self.assertEqual(self.bot.channel_id, self.test_channel_id)

    @patch("discord.Client.run")
    def test_run_bot(self, mock_super_run):
        self.bot.run_bot()
        mock_super_run.assert_called_once_with("test_token")

    @patch("logging.info")
    def test_on_ready(self, mock_logging_info):
        async def async_test():
            mock_user = MagicMock()
            mock_user.__str__ = MagicMock(return_value="TestBot#1234")

            with patch.object(type(self.bot), "user", mock_user, create=True):
                await self.bot.on_ready()

            mock_logging_info.assert_called_once_with("Bot connected as TestBot#1234")

        asyncio.run(async_test())

    def test_on_message_deletes_user_message_in_designated_channel(self):
        async def async_test():
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = MagicMock()
            mock_message.author.__str__ = MagicMock(return_value="User#1234")

            with patch.object(type(self.bot), "user", MagicMock(), create=True):
                await self.bot.on_message(mock_message)

            mock_message.delete.assert_called_once()

        asyncio.run(async_test())

    def test_on_message_ignores_bot_own_messages(self):
        async def async_test():
            mock_bot_user = MagicMock()
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = mock_bot_user

            with patch.object(type(self.bot), "user", mock_bot_user, create=True):
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

    @patch("logging.error")
    def test_on_message_handles_forbidden_error(self, mock_logging_error):
        async def async_test():
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = MagicMock()

            forbidden_exception = discord.Forbidden(response=MagicMock(), message="Missing Permissions")
            mock_message.delete = AsyncMock(side_effect=forbidden_exception)

            with patch.object(type(self.bot), "user", MagicMock(), create=True):
                await self.bot.on_message(mock_message)

            mock_logging_error.assert_called_once_with(
                f"Cannot delete messages in channel {self.test_channel_id} - missing permissions"
            )

        asyncio.run(async_test())

    @patch("logging.error")
    def test_on_message_handles_general_exception(self, mock_logging_error):
        async def async_test():
            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = self.test_channel_id
            mock_message.author = MagicMock()
            mock_message.delete = AsyncMock(side_effect=Exception("Some error"))

            with patch.object(type(self.bot), "user", MagicMock(), create=True):
                await self.bot.on_message(mock_message)

            mock_logging_error.assert_called_once_with(
                f"Failed to delete message in channel {self.test_channel_id}: Some error"
            )

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

            self.mock_store.get.return_value = ("existing_session", "existing_spectator")

            await self.bot.handle_requestid_command(mock_interaction)

            mock_interaction.user.send.assert_called_once_with(
                "Your session ID is: `existing_session`\n"
                "Your spectator ID is: `existing_spectator`\n\n"
                "**Session ID**: Use this to stream or view as the main participant.\n"
                "**Spectator ID**: Share this with others to let them watch your session without giving them control.\n\n"
                "**CAUTION**: Do not share your session ID with untrusted users!"
            )
            mock_interaction.followup.send.assert_called_once_with("Session ID sent via DM!", ephemeral=True)

        asyncio.run(async_test())

    @patch("logging.info")
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
            self.mock_store.create.return_value = ("new_session", "new_spectator")

            await self.bot.handle_requestid_command(mock_interaction)

            self.mock_store.create.assert_called_once_with("67890", "NewUser#5678")
            mock_interaction.user.send.assert_called_once_with(
                "Your session ID is: `new_session`\n"
                "Your spectator ID is: `new_spectator`\n\n"
                "**Session ID**: Use this to stream or view as the main participant.\n"
                "**Spectator ID**: Share this with others to let them watch your session without giving them control.\n\n"
                "**CAUTION**: Do not share your session ID with untrusted users!"
            )
            mock_interaction.followup.send.assert_called_once_with("Session ID sent via DM!", ephemeral=True)

        asyncio.run(async_test())

    @patch("logging.error")
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

            mock_logging_error.assert_called_once_with("ID generation failed for TestUser#1234: Creation failed")
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

            forbidden_exception = discord.Forbidden(response=MagicMock(), message="DMs disabled")
            mock_interaction.user.send = AsyncMock(side_effect=forbidden_exception)

            self.mock_store.get.return_value = ("session_id", "spectator_id")

            await self.bot.handle_requestid_command(mock_interaction)

            mock_interaction.followup.send.assert_called_once_with(
                "I couldn't DM you. Please enable DMs from server members and try again.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_requestid_command_is_registered(self):
        commands = {cmd.name: cmd for cmd in self.bot.tree.get_commands()}
        self.assertIn("requestid", commands)
        self.assertIsInstance(commands["requestid"], app_commands.Command)

    def test_renewid_command_is_registered(self):
        commands = {cmd.name: cmd for cmd in self.bot.tree.get_commands()}
        self.assertIn("renewid", commands)
        self.assertIsInstance(commands["renewid"], app_commands.Command)

    def test_requestid_command_calls_handler(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id

            commands = {cmd.name: cmd for cmd in self.bot.tree.get_commands()}
            with patch.object(self.bot, "handle_requestid_command") as mock_handler:
                await commands["requestid"].callback(mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction)

        asyncio.run(async_test())

    def test_renewid_command_calls_handler(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.channel_id = self.test_channel_id

            commands = {cmd.name: cmd for cmd in self.bot.tree.get_commands()}
            with patch.object(self.bot, "handle_renewid_command") as mock_handler:
                await commands["renewid"].callback(mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction)

        asyncio.run(async_test())

    def test_init_with_testdrive_channel_id(self):
        with (
            patch("v3xctrl_relay.discord_bot.Bot.SessionStore") as mock_ss,
            patch("v3xctrl_relay.discord_bot.Bot.TestdriveHandler") as mock_td,
        ):
            mock_ss.return_value = MagicMock()
            mock_td_instance = MagicMock()
            mock_td.return_value = mock_td_instance

            bot = Bot(
                db_path="test.db",
                token="test_token",
                channel_id=123456789,
                testdrive_channel_id=987654321,
            )

            self.assertEqual(bot.testdrive_channel_id, 987654321)
            self.assertEqual(bot.testdrive_handler, mock_td_instance)
            mock_td.assert_called_once_with(mock_ss.return_value, 987654321)

    def test_init_without_testdrive_channel_id(self):
        self.assertIsNone(self.bot.testdrive_channel_id)
        self.assertIsNone(self.bot.testdrive_handler)

    def test_on_message_deletes_in_testdrive_channel(self):
        async def async_test():
            with (
                patch("v3xctrl_relay.discord_bot.Bot.SessionStore") as mock_ss,
                patch("v3xctrl_relay.discord_bot.Bot.TestdriveHandler"),
            ):
                mock_ss.return_value = MagicMock()
                bot = Bot(
                    db_path="test.db",
                    token="test_token",
                    channel_id=123456789,
                    testdrive_channel_id=987654321,
                )

            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = 987654321
            mock_message.author = MagicMock()

            with patch.object(type(bot), "user", MagicMock(), create=True):
                await bot.on_message(mock_message)

            mock_message.delete.assert_called_once()

        asyncio.run(async_test())

    def test_on_message_ignores_other_channels_with_testdrive(self):
        async def async_test():
            with (
                patch("v3xctrl_relay.discord_bot.Bot.SessionStore") as mock_ss,
                patch("v3xctrl_relay.discord_bot.Bot.TestdriveHandler"),
            ):
                mock_ss.return_value = MagicMock()
                bot = Bot(
                    db_path="test.db",
                    token="test_token",
                    channel_id=123456789,
                    testdrive_channel_id=987654321,
                )

            mock_message = AsyncMock(spec=discord.Message)
            mock_message.channel = MagicMock()
            mock_message.channel.id = 111111111
            mock_message.author = MagicMock()

            await bot.on_message(mock_message)

            mock_message.delete.assert_not_called()

        asyncio.run(async_test())

    def test_on_interaction_routes_to_testdrive_handler(self):
        async def async_test():
            mock_td_handler = AsyncMock()

            with (
                patch("v3xctrl_relay.discord_bot.Bot.SessionStore") as mock_ss,
                patch("v3xctrl_relay.discord_bot.Bot.TestdriveHandler") as mock_td,
            ):
                mock_ss.return_value = MagicMock()
                mock_td.return_value = mock_td_handler
                bot = Bot(
                    db_path="test.db",
                    token="test_token",
                    channel_id=123456789,
                    testdrive_channel_id=987654321,
                )

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component

            await bot.on_interaction(mock_interaction)

            mock_td_handler.handle_interaction.assert_called_once_with(mock_interaction)

        asyncio.run(async_test())

    def test_on_interaction_ignores_slash_commands(self):
        async def async_test():
            mock_td_handler = AsyncMock()

            with (
                patch("v3xctrl_relay.discord_bot.Bot.SessionStore") as mock_ss,
                patch("v3xctrl_relay.discord_bot.Bot.TestdriveHandler") as mock_td,
            ):
                mock_ss.return_value = MagicMock()
                mock_td.return_value = mock_td_handler
                bot = Bot(
                    db_path="test.db",
                    token="test_token",
                    channel_id=123456789,
                    testdrive_channel_id=987654321,
                )

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.application_command

            await bot.on_interaction(mock_interaction)

            mock_td_handler.handle_interaction.assert_not_called()

        asyncio.run(async_test())

    def test_on_interaction_ignores_when_no_testdrive_handler(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component

            # self.bot has no testdrive handler (default setUp)
            await self.bot.on_interaction(mock_interaction)

        asyncio.run(async_test())

    def test_on_ready_posts_testdrive_message(self):
        async def async_test():
            mock_td_handler = AsyncMock()

            with (
                patch("v3xctrl_relay.discord_bot.Bot.SessionStore") as mock_ss,
                patch("v3xctrl_relay.discord_bot.Bot.TestdriveHandler") as mock_td,
            ):
                mock_ss.return_value = MagicMock()
                mock_td.return_value = mock_td_handler
                bot = Bot(
                    db_path="test.db",
                    token="test_token",
                    channel_id=123456789,
                    testdrive_channel_id=987654321,
                )

            mock_channel = MagicMock(spec=discord.TextChannel)
            mock_user = MagicMock()
            mock_user.__str__ = MagicMock(return_value="TestBot#1234")

            with (
                patch.object(type(bot), "user", mock_user, create=True),
                patch.object(bot, "get_channel") as mock_get_channel,
                patch.object(bot, "_announce_presence"),
            ):
                mock_get_channel.return_value = mock_channel
                await bot._announce_testdrive()

            mock_td_handler.post_persistent_message.assert_called_once_with(mock_channel)

        asyncio.run(async_test())


if __name__ == "__main__":
    unittest.main()
