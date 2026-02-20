import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from v3xctrl_udp_relay.discord_bot.testdrive import (
    CUSTOM_ID_ACCEPT_PREFIX,
    CUSTOM_ID_CANCEL_PREFIX,
    CUSTOM_ID_INVALIDATE_PREFIX,
    CUSTOM_ID_RATE_PREFIX,
    CUSTOM_ID_REQUEST,
    TestdriveHandler,
)


class AsyncIteratorMock:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


class TestTestdriveHandler(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.testdrive_channel_id = 987654321
        self.handler = TestdriveHandler(self.mock_store, self.testdrive_channel_id)

    # --- _has_pending_or_active_testdrive ---

    def test_has_pending_request_returns_true(self):
        self.handler.pending_requests["12345"] = 99999
        self.mock_store.get_testdrive_by_user.return_value = None

        self.assertTrue(self.handler._has_pending_or_active_testdrive("12345"))

    def test_has_active_testdrive_returns_true(self):
        self.mock_store.get_testdrive_by_user.return_value = ("sid", "spec", "12345:67890")

        self.assertTrue(self.handler._has_pending_or_active_testdrive("12345"))

    def test_no_pending_or_active_returns_false(self):
        self.mock_store.get_testdrive_by_user.return_value = None

        self.assertFalse(self.handler._has_pending_or_active_testdrive("12345"))

    # --- post_persistent_message ---

    def test_post_persistent_message(self):
        async def async_test():
            mock_channel = AsyncMock(spec=discord.TextChannel)

            with patch.object(self.handler, '_delete_old_announcement'):
                await self.handler.post_persistent_message(mock_channel)

            mock_channel.send.assert_called_once()
            call_args = mock_channel.send.call_args
            self.assertIn("Test Drive", call_args.args[0])
            self.assertIsNotNone(call_args.kwargs.get("view"))

        asyncio.run(async_test())

    def test_post_persistent_message_deletes_old_announcement(self):
        async def async_test():
            mock_channel = AsyncMock(spec=discord.TextChannel)

            with patch.object(self.handler, '_delete_old_announcement') as mock_delete:
                await self.handler.post_persistent_message(mock_channel)

            mock_delete.assert_called_once_with(mock_channel)

        asyncio.run(async_test())

    @patch('logging.error')
    def test_post_persistent_message_forbidden(self, mock_logging_error):
        async def async_test():
            mock_channel = AsyncMock(spec=discord.TextChannel)
            mock_channel.send = AsyncMock(
                side_effect=discord.Forbidden(response=MagicMock(), message="Missing Permissions")
            )

            with patch.object(self.handler, '_delete_old_announcement'):
                await self.handler.post_persistent_message(mock_channel)

            mock_logging_error.assert_called_once()

        asyncio.run(async_test())

    # --- _delete_old_announcement ---

    def test_delete_old_announcement_removes_announcement(self):
        async def async_test():
            mock_bot_user = MagicMock()

            mock_button = MagicMock()
            mock_button.custom_id = CUSTOM_ID_REQUEST
            mock_row = MagicMock()
            mock_row.children = [mock_button]

            old_announcement = AsyncMock(spec=discord.Message)
            old_announcement.author = mock_bot_user
            old_announcement.components = [mock_row]

            mock_channel = AsyncMock(spec=discord.TextChannel)
            mock_channel.guild.me = mock_bot_user
            mock_channel.history.return_value = AsyncIteratorMock([old_announcement])

            await self.handler._delete_old_announcement(mock_channel)

            old_announcement.delete.assert_called_once()

        asyncio.run(async_test())

    def test_delete_old_announcement_preserves_history_messages(self):
        async def async_test():
            mock_bot_user = MagicMock()

            # A testdrive history message (no td_request button)
            mock_button = MagicMock()
            mock_button.custom_id = f"{CUSTOM_ID_INVALIDATE_PREFIX}111:222"
            mock_row = MagicMock()
            mock_row.children = [mock_button]

            history_msg = AsyncMock(spec=discord.Message)
            history_msg.author = mock_bot_user
            history_msg.components = [mock_row]

            # A message with no components (edited completed testdrive)
            plain_msg = AsyncMock(spec=discord.Message)
            plain_msg.author = mock_bot_user
            plain_msg.components = []

            mock_channel = AsyncMock(spec=discord.TextChannel)
            mock_channel.guild.me = mock_bot_user
            mock_channel.history.return_value = AsyncIteratorMock(
                [history_msg, plain_msg]
            )

            await self.handler._delete_old_announcement(mock_channel)

            history_msg.delete.assert_not_called()
            plain_msg.delete.assert_not_called()

        asyncio.run(async_test())

    def test_delete_old_announcement_ignores_other_users(self):
        async def async_test():
            mock_bot_user = MagicMock()
            mock_other_user = MagicMock()

            other_msg = AsyncMock(spec=discord.Message)
            other_msg.author = mock_other_user
            other_msg.components = []

            mock_channel = AsyncMock(spec=discord.TextChannel)
            mock_channel.guild.me = mock_bot_user
            mock_channel.history.return_value = AsyncIteratorMock([other_msg])

            await self.handler._delete_old_announcement(mock_channel)

            other_msg.delete.assert_not_called()

        asyncio.run(async_test())

    # --- _is_announcement_message ---

    def test_is_announcement_message_true(self):
        mock_button = MagicMock()
        mock_button.custom_id = CUSTOM_ID_REQUEST
        mock_row = MagicMock()
        mock_row.children = [mock_button]

        mock_message = MagicMock(spec=discord.Message)
        mock_message.components = [mock_row]

        self.assertTrue(TestdriveHandler._is_announcement_message(mock_message))

    def test_is_announcement_message_false_different_button(self):
        mock_button = MagicMock()
        mock_button.custom_id = f"{CUSTOM_ID_INVALIDATE_PREFIX}111:222"
        mock_row = MagicMock()
        mock_row.children = [mock_button]

        mock_message = MagicMock(spec=discord.Message)
        mock_message.components = [mock_row]

        self.assertFalse(TestdriveHandler._is_announcement_message(mock_message))

    def test_is_announcement_message_false_no_components(self):
        mock_message = MagicMock(spec=discord.Message)
        mock_message.components = []

        self.assertFalse(TestdriveHandler._is_announcement_message(mock_message))

    # --- handle_interaction dispatch ---

    def test_dispatch_ignores_non_component_interaction(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.application_command

            await self.handler.handle_interaction(mock_interaction)

        asyncio.run(async_test())

    def test_dispatch_ignores_non_td_custom_id(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component
            mock_interaction.data = {"custom_id": "other_button"}

            with patch.object(self.handler, '_handle_request') as mock_handler:
                await self.handler.handle_interaction(mock_interaction)
                mock_handler.assert_not_called()

        asyncio.run(async_test())

    def test_dispatch_td_request(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component
            mock_interaction.data = {"custom_id": CUSTOM_ID_REQUEST}

            with patch.object(self.handler, '_handle_request') as mock_handler:
                await self.handler.handle_interaction(mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction)

        asyncio.run(async_test())

    def test_dispatch_td_cancel(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component
            mock_interaction.data = {"custom_id": f"{CUSTOM_ID_CANCEL_PREFIX}12345"}

            with patch.object(self.handler, '_handle_cancel') as mock_handler:
                await self.handler.handle_interaction(mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction, "12345")

        asyncio.run(async_test())

    def test_dispatch_td_accept(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component
            mock_interaction.data = {"custom_id": f"{CUSTOM_ID_ACCEPT_PREFIX}12345"}

            with patch.object(self.handler, '_handle_accept') as mock_handler:
                await self.handler.handle_interaction(mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction, "12345")

        asyncio.run(async_test())

    def test_dispatch_td_invalidate(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component
            mock_interaction.data = {"custom_id": f"{CUSTOM_ID_INVALIDATE_PREFIX}111:222"}

            with patch.object(self.handler, '_handle_invalidate') as mock_handler:
                await self.handler.handle_interaction(mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction, "111", "222")

        asyncio.run(async_test())

    def test_dispatch_td_rate(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component
            mock_interaction.data = {"custom_id": f"{CUSTOM_ID_RATE_PREFIX}111:222:4"}

            with patch.object(self.handler, '_handle_rate') as mock_handler:
                await self.handler.handle_interaction(mock_interaction)
                mock_handler.assert_called_once_with(mock_interaction, "111", "222", 4)

        asyncio.run(async_test())

    # --- _handle_request ---

    def test_request_creates_pending_message(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.type = discord.InteractionType.component
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.user.mention = "<@12345>"
            mock_interaction.response = AsyncMock()

            mock_guild = MagicMock()
            host_role = MagicMock()
            host_role.mention = "<@&host>"
            mock_guild.roles = [host_role]
            mock_interaction.guild = mock_guild

            mock_message = AsyncMock()
            mock_message.id = 99999
            mock_channel = AsyncMock(spec=discord.TextChannel)
            mock_channel.send = AsyncMock(return_value=mock_message)
            mock_interaction.channel = mock_channel

            self.mock_store.get_testdrive_by_user.return_value = None

            with patch('discord.utils.get', return_value=host_role):
                await self.handler._handle_request(mock_interaction)

            self.assertIn("12345", self.handler.pending_requests)
            self.assertEqual(self.handler.pending_requests["12345"], 99999)
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_channel.send.assert_called_once()

        asyncio.run(async_test())

    def test_request_blocked_when_pending_exists(self):
        async def async_test():
            self.handler.pending_requests["12345"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.response = AsyncMock()

            self.mock_store.get_testdrive_by_user.return_value = None

            await self.handler._handle_request(mock_interaction)

            mock_interaction.response.send_message.assert_called_once_with(
                "You already have a pending or active test drive.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_request_blocked_when_active_session_exists(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.response = AsyncMock()

            self.mock_store.get_testdrive_by_user.return_value = ("sid", "spec", "12345:67890")

            await self.handler._handle_request(mock_interaction)

            mock_interaction.response.send_message.assert_called_once_with(
                "You already have a pending or active test drive.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_request_requires_guild(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.guild = None
            mock_interaction.response = AsyncMock()

            self.mock_store.get_testdrive_by_user.return_value = None

            await self.handler._handle_request(mock_interaction)

            mock_interaction.response.send_message.assert_called_once_with(
                "This can only be used in a server.", ephemeral=True
            )

        asyncio.run(async_test())

    # --- _handle_cancel ---

    def test_cancel_by_requester_succeeds(self):
        async def async_test():
            self.handler.pending_requests["12345"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.user.mention = "<@12345>"
            mock_interaction.message = AsyncMock()
            mock_interaction.response = AsyncMock()

            await self.handler._handle_cancel(mock_interaction, "12345")

            self.assertNotIn("12345", self.handler.pending_requests)
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.message.edit.assert_called_once()
            call_kwargs = mock_interaction.message.edit.call_args.kwargs
            self.assertIn("cancelled", call_kwargs["content"])
            self.assertIsNone(call_kwargs["view"])

        asyncio.run(async_test())

    def test_cancel_by_other_user_rejected(self):
        async def async_test():
            self.handler.pending_requests["12345"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 67890
            mock_interaction.response = AsyncMock()

            await self.handler._handle_cancel(mock_interaction, "12345")

            self.assertIn("12345", self.handler.pending_requests)
            mock_interaction.response.send_message.assert_called_once_with(
                "Only the requester can cancel this request.", ephemeral=True
            )

        asyncio.run(async_test())

    # --- _handle_accept ---

    def test_accept_creates_session_and_dms_both(self):
        async def async_test():
            self.handler.pending_requests["12345"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 67890
            mock_interaction.user.mention = "<@67890>"
            mock_interaction.user.__str__ = MagicMock(return_value="HostUser#1234")
            mock_interaction.user.send = AsyncMock()
            mock_interaction.message = AsyncMock()
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()

            mock_guest = AsyncMock()
            mock_guest.send = AsyncMock()
            mock_interaction.client = AsyncMock()
            mock_interaction.client.fetch_user = AsyncMock(return_value=mock_guest)

            self.mock_store.create.return_value = ("test_session", "test_spectator")

            await self.handler._handle_accept(mock_interaction, "12345")

            self.mock_store.create.assert_called_once_with("12345:67890", "12345:HostUser#1234")
            self.assertNotIn("12345", self.handler.pending_requests)

            # Host gets both IDs
            host_dm = mock_interaction.user.send.call_args.args[0]
            self.assertIn("test_session", host_dm)
            self.assertIn("test_spectator", host_dm)

            # Guest gets only session ID
            guest_dm = mock_guest.send.call_args.args[0]
            self.assertIn("test_session", guest_dm)
            self.assertNotIn("test_spectator", guest_dm)

            # Message edited with active view (5 star buttons + invalidate)
            mock_interaction.message.edit.assert_called_once()
            edit_kwargs = mock_interaction.message.edit.call_args.kwargs
            self.assertIn("Session IDs have been generated and sent via PM", edit_kwargs["content"])
            active_view = edit_kwargs["view"]
            self.assertIsNotNone(active_view)
            self.assertEqual(len(active_view.children), 6)

        asyncio.run(async_test())

    def test_accept_request_no_longer_available(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 67890
            mock_interaction.response = AsyncMock()

            await self.handler._handle_accept(mock_interaction, "12345")

            mock_interaction.response.send_message.assert_called_once_with(
                "This request is no longer available.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_accept_own_request_rejected(self):
        async def async_test():
            self.handler.pending_requests["12345"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 12345
            mock_interaction.response = AsyncMock()

            await self.handler._handle_accept(mock_interaction, "12345")

            mock_interaction.response.send_message.assert_called_once_with(
                "You cannot accept your own request.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_accept_session_creation_failure(self):
        async def async_test():
            self.handler.pending_requests["12345"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 67890
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()

            self.mock_store.create.side_effect = RuntimeError("DB error")

            await self.handler._handle_accept(mock_interaction, "12345")

            mock_interaction.followup.send.assert_called_once()
            self.assertIn("12345", self.handler.pending_requests)

        asyncio.run(async_test())

    def test_accept_dm_failure_rolls_back(self):
        async def async_test():
            self.handler.pending_requests["12345"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 67890
            mock_interaction.user.mention = "<@67890>"
            mock_interaction.user.__str__ = MagicMock(return_value="HostUser#1234")
            mock_interaction.user.send = AsyncMock(
                side_effect=discord.Forbidden(response=MagicMock(), message="DMs disabled")
            )
            mock_interaction.message = AsyncMock()
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()
            mock_interaction.client = AsyncMock()
            mock_interaction.client.fetch_user = AsyncMock(return_value=AsyncMock())

            self.mock_store.create.return_value = ("test_session", "test_spectator")

            await self.handler._handle_accept(mock_interaction, "12345")

            self.mock_store.delete.assert_called_once_with("12345:67890")
            self.assertNotIn("12345", self.handler.pending_requests)

        asyncio.run(async_test())

    def test_accept_composed_key_format(self):
        async def async_test():
            self.handler.pending_requests["111"] = 99999

            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 222
            mock_interaction.user.mention = "<@222>"
            mock_interaction.user.__str__ = MagicMock(return_value="Host#0001")
            mock_interaction.user.send = AsyncMock()
            mock_interaction.message = AsyncMock()
            mock_interaction.response = AsyncMock()
            mock_interaction.followup = AsyncMock()
            mock_interaction.client = AsyncMock()
            mock_interaction.client.fetch_user = AsyncMock(return_value=AsyncMock())

            self.mock_store.create.return_value = ("sid", "spec")

            await self.handler._handle_accept(mock_interaction, "111")

            self.mock_store.create.assert_called_once_with("111:222", "111:Host#0001")

        asyncio.run(async_test())

    # --- _handle_invalidate ---

    def test_invalidate_by_host_succeeds(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 222
            mock_interaction.user.mention = "<@222>"
            mock_interaction.message = AsyncMock()
            mock_interaction.message.content = "some message without rating"
            mock_interaction.response = AsyncMock()

            await self.handler._handle_invalidate(mock_interaction, "111", "222")

            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            self.mock_store.delete.assert_called_once_with("111:222")
            mock_interaction.message.edit.assert_called_once()
            edit_kwargs = mock_interaction.message.edit.call_args.kwargs
            self.assertIn("invalidated", edit_kwargs["content"])
            self.assertIn("let us know how you liked it", edit_kwargs["content"])
            # Rating buttons should still be shown
            view = edit_kwargs["view"]
            self.assertIsNotNone(view)
            self.assertEqual(len(view.children), 5)
            for i in range(5):
                self.assertEqual(view.children[i].custom_id, f"{CUSTOM_ID_RATE_PREFIX}111:222:{i + 1}")

        asyncio.run(async_test())

    def test_invalidate_preserves_rating(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 222
            mock_interaction.user.mention = "<@222>"
            mock_interaction.message = AsyncMock()
            mock_interaction.message.content = (
                "<@111> requested a test ride. <@222> hosted them.\n\n"
                "<@111> rated their experience: ★★★★☆"
            )
            mock_interaction.response = AsyncMock()

            await self.handler._handle_invalidate(mock_interaction, "111", "222")

            edit_kwargs = mock_interaction.message.edit.call_args.kwargs
            self.assertIn("invalidated", edit_kwargs["content"])
            self.assertIn("rated their experience: ★★★★☆", edit_kwargs["content"])
            self.assertIsNone(edit_kwargs["view"])

        asyncio.run(async_test())

    def test_invalidate_by_non_host_rejected(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 999
            mock_interaction.response = AsyncMock()

            await self.handler._handle_invalidate(mock_interaction, "111", "222")

            self.mock_store.delete.assert_not_called()
            mock_interaction.response.send_message.assert_called_once_with(
                "Only the host can invalidate this session.", ephemeral=True
            )

        asyncio.run(async_test())

    # --- View construction ---

    def test_make_request_view(self):
        async def async_test():
            view = self.handler._make_request_view()
            self.assertIsInstance(view, discord.ui.View)
            self.assertIsNone(view.timeout)
            self.assertEqual(len(view.children), 1)
            self.assertEqual(view.children[0].custom_id, CUSTOM_ID_REQUEST)

        asyncio.run(async_test())

    def test_make_pending_view(self):
        async def async_test():
            view = self.handler._make_pending_view("12345")
            self.assertIsInstance(view, discord.ui.View)
            self.assertIsNone(view.timeout)
            self.assertEqual(len(view.children), 2)
            custom_ids = {child.custom_id for child in view.children}
            self.assertIn(f"{CUSTOM_ID_ACCEPT_PREFIX}12345", custom_ids)
            self.assertIn(f"{CUSTOM_ID_CANCEL_PREFIX}12345", custom_ids)

        asyncio.run(async_test())

    def test_make_invalidate_view(self):
        async def async_test():
            view = self.handler._make_invalidate_view("111", "222")
            self.assertIsInstance(view, discord.ui.View)
            self.assertIsNone(view.timeout)
            self.assertEqual(len(view.children), 1)
            self.assertEqual(view.children[0].custom_id, f"{CUSTOM_ID_INVALIDATE_PREFIX}111:222")

        asyncio.run(async_test())

    def test_make_rating_view(self):
        async def async_test():
            view = self.handler._make_rating_view("111", "222")
            self.assertIsInstance(view, discord.ui.View)
            self.assertIsNone(view.timeout)
            self.assertEqual(len(view.children), 5)

            for i in range(5):
                child = view.children[i]
                self.assertEqual(child.custom_id, f"{CUSTOM_ID_RATE_PREFIX}111:222:{i + 1}")
                self.assertEqual(child.label, "★" * (i + 1))

        asyncio.run(async_test())

    def test_make_active_view(self):
        async def async_test():
            view = self.handler._make_active_view("111", "222")
            self.assertIsInstance(view, discord.ui.View)
            self.assertIsNone(view.timeout)
            self.assertEqual(len(view.children), 6)

            # First 5 are star rating buttons
            for i in range(5):
                child = view.children[i]
                self.assertEqual(child.custom_id, f"{CUSTOM_ID_RATE_PREFIX}111:222:{i + 1}")
                self.assertEqual(child.label, "★" * (i + 1))

            # Last is invalidate button
            self.assertEqual(view.children[5].custom_id, f"{CUSTOM_ID_INVALIDATE_PREFIX}111:222")

        asyncio.run(async_test())

    # --- _handle_rate ---

    def test_rate_by_guest_succeeds(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 111
            mock_interaction.message = AsyncMock()
            mock_interaction.message.content = "some active session message"
            mock_interaction.response = AsyncMock()

            await self.handler._handle_rate(mock_interaction, "111", "222", 4)

            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.message.edit.assert_called_once()
            edit_kwargs = mock_interaction.message.edit.call_args.kwargs
            self.assertIn("rated their experience: ★★★★☆", edit_kwargs["content"])
            self.assertNotIn("invalidated", edit_kwargs["content"])
            # View should be invalidate-only (rating buttons removed)
            view = edit_kwargs["view"]
            self.assertEqual(len(view.children), 1)
            self.assertEqual(view.children[0].custom_id, f"{CUSTOM_ID_INVALIDATE_PREFIX}111:222")

        asyncio.run(async_test())

    def test_rate_after_invalidation(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 111
            mock_interaction.message = AsyncMock()
            mock_interaction.message.content = (
                "<@111> requested a test ride. <@222> hosted them.\n"
                "Session has been invalidated.\n\n"
                "<@111>, let us know how you liked it!"
            )
            mock_interaction.response = AsyncMock()

            await self.handler._handle_rate(mock_interaction, "111", "222", 3)

            edit_kwargs = mock_interaction.message.edit.call_args.kwargs
            self.assertIn("rated their experience: ★★★☆☆", edit_kwargs["content"])
            self.assertIn("invalidated", edit_kwargs["content"])
            self.assertIsNone(edit_kwargs["view"])

        asyncio.run(async_test())

    def test_rate_by_non_guest_rejected(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 999
            mock_interaction.response = AsyncMock()

            await self.handler._handle_rate(mock_interaction, "111", "222", 3)

            mock_interaction.response.send_message.assert_called_once_with(
                "Only the guest can rate this test drive.", ephemeral=True
            )

        asyncio.run(async_test())

    def test_rate_invalid_stars_ignored(self):
        async def async_test():
            mock_interaction = AsyncMock(spec=discord.Interaction)
            mock_interaction.user = MagicMock()
            mock_interaction.user.id = 111
            mock_interaction.response = AsyncMock()

            await self.handler._handle_rate(mock_interaction, "111", "222", 0)
            await self.handler._handle_rate(mock_interaction, "111", "222", 6)

            mock_interaction.response.defer.assert_not_called()
            mock_interaction.message.edit.assert_not_called()

        asyncio.run(async_test())

    def test_rate_all_star_values(self):
        async def async_test():
            expected = {
                1: "★☆☆☆☆",
                2: "★★☆☆☆",
                3: "★★★☆☆",
                4: "★★★★☆",
                5: "★★★★★",
            }
            for stars, display in expected.items():
                mock_interaction = AsyncMock(spec=discord.Interaction)
                mock_interaction.user = MagicMock()
                mock_interaction.user.id = 111
                mock_interaction.message = AsyncMock()
                mock_interaction.message.content = "active session"
                mock_interaction.response = AsyncMock()

                await self.handler._handle_rate(mock_interaction, "111", "222", stars)

                edit_kwargs = mock_interaction.message.edit.call_args.kwargs
                self.assertIn(display, edit_kwargs["content"])

        asyncio.run(async_test())


if __name__ == '__main__':
    unittest.main()
