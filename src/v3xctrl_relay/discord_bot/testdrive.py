import logging

import discord

from v3xctrl_relay.SessionStore import SessionStore

logger = logging.getLogger(__name__)

CUSTOM_ID_REQUEST = "td_request"
CUSTOM_ID_CANCEL_PREFIX = "td_cancel:"
CUSTOM_ID_ACCEPT_PREFIX = "td_accept:"
CUSTOM_ID_INVALIDATE_PREFIX = "td_invalidate:"
CUSTOM_ID_RATE_PREFIX = "td_rate:"


class TestdriveHandler:
    def __init__(self, store: SessionStore, testdrive_channel_id: int) -> None:
        self.store = store
        self.testdrive_channel_id = testdrive_channel_id
        self.pending_requests: dict[str, int] = {}

    async def post_persistent_message(self, channel: discord.TextChannel) -> None:
        await self._delete_old_announcement(channel)

        announcement = (
            "## Test Drive\n\n"
            "Want to take the RC car for a spin? Click the button below to request a test drive!\n\n"
            "### Before You Request\n"
            "Please make sure you have everything set up **before** requesting a test drive:\n"
            "1. [Download and install the viewer](<https://github.com/stylesuxx/v3xctrl/wiki/Viewer>)\n"
            "2. [Set up and calibrate your controller](<https://github.com/stylesuxx/v3xctrl/wiki/Controller-Setup>)\n\n"
            "> **Note:** A host needs to accept your request, which may take some time "
            "due to timezone differences and availability. "
            "This is a hobby project and we do this in our spare time, so please be patient. "
            "Things might not always go perfectly - but that's part of the fun!"
        )

        try:
            await channel.send(announcement, view=self._make_request_view())
        except discord.Forbidden:
            logger.error(f"Cannot send testdrive message to channel {self.testdrive_channel_id} - missing permissions")
        except Exception as e:
            logger.error(f"Failed to post testdrive message in channel {self.testdrive_channel_id}: {e}")

    async def _delete_old_announcement(self, channel: discord.TextChannel) -> None:
        try:
            async for message in channel.history(limit=100):
                if message.author != channel.guild.me:
                    continue

                if self._is_announcement_message(message):
                    await message.delete()
        except Exception as e:
            logger.error(f"Failed to clean up old announcements: {e}")

    @staticmethod
    def _is_announcement_message(message: discord.Message) -> bool:
        for row in message.components:
            for child in row.children:
                if getattr(child, "custom_id", None) == CUSTOM_ID_REQUEST:
                    return True
        return False

    async def handle_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")

        if not custom_id.startswith("td_"):
            return

        if custom_id == CUSTOM_ID_REQUEST:
            await self._handle_request(interaction)
        elif custom_id.startswith(CUSTOM_ID_CANCEL_PREFIX):
            requester_id = custom_id[len(CUSTOM_ID_CANCEL_PREFIX) :]
            await self._handle_cancel(interaction, requester_id)
        elif custom_id.startswith(CUSTOM_ID_ACCEPT_PREFIX):
            requester_id = custom_id[len(CUSTOM_ID_ACCEPT_PREFIX) :]
            await self._handle_accept(interaction, requester_id)
        elif custom_id.startswith(CUSTOM_ID_INVALIDATE_PREFIX):
            parts = custom_id[len(CUSTOM_ID_INVALIDATE_PREFIX) :].split(":", 1)
            if len(parts) == 2:
                guest_id, host_id = parts
                await self._handle_invalidate(interaction, guest_id, host_id)
        elif custom_id.startswith(CUSTOM_ID_RATE_PREFIX):
            parts = custom_id[len(CUSTOM_ID_RATE_PREFIX) :].split(":", 2)
            if len(parts) == 3:
                guest_id, host_id, stars = parts
                await self._handle_rate(interaction, guest_id, host_id, int(stars))

    def _has_pending_or_active_testdrive(self, user_id: str) -> bool:
        if user_id in self.pending_requests:
            return True

        return self.store.get_testdrive_by_user(user_id) is not None

    async def _handle_request(self, interaction: discord.Interaction) -> None:
        requester_id = str(interaction.user.id)

        if self._has_pending_or_active_testdrive(requester_id):
            await interaction.response.send_message("You already have a pending or active test drive.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        host_role = discord.utils.get(interaction.guild.roles, name="host")
        role_mention = host_role.mention if host_role else "@host"

        message = await interaction.channel.send(
            f"Hey {role_mention}, {interaction.user.mention} would like a test ride - who wants to host them?",
            view=self._make_pending_view(requester_id),
            allowed_mentions=discord.AllowedMentions(roles=True, users=True),
        )

        self.pending_requests[requester_id] = message.id

    async def _handle_cancel(self, interaction: discord.Interaction, requester_id: str) -> None:
        if str(interaction.user.id) != requester_id:
            await interaction.response.send_message("Only the requester can cancel this request.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        self.pending_requests.pop(requester_id, None)

        await interaction.message.edit(
            content=f"{interaction.user.mention}'s test drive request was cancelled.", view=None
        )

    async def _handle_accept(self, interaction: discord.Interaction, requester_id: str) -> None:
        if requester_id not in self.pending_requests:
            await interaction.response.send_message("This request is no longer available.", ephemeral=True)
            return

        host_id = str(interaction.user.id)

        if host_id == requester_id:
            await interaction.response.send_message("You cannot accept your own request.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        composed_key = f"{requester_id}:{host_id}"
        username = f"{requester_id}:{interaction.user}"

        try:
            session_id, spectator_id = self.store.create(composed_key, username)
        except RuntimeError as e:
            logger.error(f"Failed to create testdrive session: {e}")
            await interaction.followup.send("Failed to create session. Please try again.", ephemeral=True)
            return

        self.pending_requests.pop(requester_id, None)

        guest_user = None
        dm_failed = False

        try:
            guest_user = await interaction.client.fetch_user(int(requester_id))
        except Exception as e:
            logger.error(f"Failed to fetch guest user {requester_id}: {e}")
            dm_failed = True

        try:
            await interaction.user.send(
                f"You are hosting a test drive for <@{requester_id}>!\n\n"
                f"**Session ID:** `{session_id}`\n"
                f"**Spectator ID:** `{spectator_id}`\n\n"
                "Configure your rig with the session ID. "
                "Share the spectator ID with anyone who wants to watch."
            )
        except discord.Forbidden:
            logger.error(f"Cannot DM host {interaction.user} - DMs disabled")
            dm_failed = True

        if guest_user:
            try:
                await guest_user.send(
                    f"Your test drive has been accepted by {interaction.user.mention}!\n\n"
                    f"**Session ID:** `{session_id}`\n\n"
                    "Use this session ID to connect and drive.\n\n"
                    "You will need a viewer to connect. Download one from the "
                    "[releases page](https://github.com/stylesuxx/v3xctrl/releases).\n\n"
                    "It is highly recommended to use a gamepad or wheel instead of the keyboard. "
                    "You can calibrate your input device in the viewer beforehand."
                )
            except discord.Forbidden:
                logger.error(f"Cannot DM guest {guest_user} - DMs disabled")
                dm_failed = True

        if dm_failed:
            self.store.delete(composed_key)
            await interaction.message.edit(
                content=(
                    f"<@{requester_id}> requested a test ride, {interaction.user.mention} tried to accept "
                    f"but session IDs could not be delivered via DM. "
                    f"Please make sure DMs from server members are enabled and try again."
                ),
                view=None,
            )
            await interaction.followup.send(
                "Could not deliver session IDs via DM. The session has been rolled back. "
                "Ensure both you and the requester have DMs enabled from server members.",
                ephemeral=True,
            )
            return

        await interaction.message.edit(
            content=(
                f"<@{requester_id}> requested a test ride, {interaction.user.mention} offered them a rig.\n"
                f"Session IDs have been generated and sent via PM.\n\n"
                f"Have fun!\n\n"
                f"<@{requester_id}>, let us know how you liked it!"
            ),
            view=self._make_active_view(requester_id, host_id),
        )

    async def _handle_invalidate(self, interaction: discord.Interaction, guest_id: str, host_id: str) -> None:
        if str(interaction.user.id) != host_id:
            await interaction.response.send_message("Only the host can invalidate this session.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        composed_key = f"{guest_id}:{host_id}"
        self.store.delete(composed_key)

        current_content = interaction.message.content or ""
        rating_section = ""
        for line in current_content.split("\n"):
            if "rated their experience:" in line:
                rating_section = f"\n\n{line}"
                break

        has_rating = bool(rating_section)
        view = None if has_rating else self._make_rating_view(guest_id, host_id)

        content = (
            f"<@{guest_id}> requested a test ride. <@{host_id}> hosted them.\n"
            f"Session has been invalidated."
            f"{rating_section}"
        )

        if not has_rating:
            content += f"\n\n<@{guest_id}>, let us know how you liked it!"

        await interaction.message.edit(content=content, view=view)

    async def _handle_rate(self, interaction: discord.Interaction, guest_id: str, host_id: str, stars: int) -> None:
        if str(interaction.user.id) != guest_id:
            await interaction.response.send_message("Only the guest can rate this test drive.", ephemeral=True)
            return

        if not 1 <= stars <= 5:
            return

        await interaction.response.defer(ephemeral=True)

        rating_display = "★" * stars + "☆" * (5 - stars)

        current_content = interaction.message.content or ""
        is_invalidated = "invalidated" in current_content

        if is_invalidated:
            content = (
                f"<@{guest_id}> requested a test ride. <@{host_id}> hosted them.\n"
                f"Session has been invalidated.\n\n"
                f"<@{guest_id}> rated their experience: {rating_display}"
            )
            view = None
        else:
            content = (
                f"<@{guest_id}> requested a test ride. <@{host_id}> hosted them.\n\n"
                f"<@{guest_id}> rated their experience: {rating_display}"
            )
            view = self._make_invalidate_view(guest_id, host_id)

        await interaction.message.edit(content=content, view=view)

    def _make_request_view(self) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(
            label="Request Test Drive", style=discord.ButtonStyle.green, custom_id=CUSTOM_ID_REQUEST
        )
        view.add_item(button)
        return view

    def _make_pending_view(self, requester_id: str) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        accept = discord.ui.Button(
            label="Accept", style=discord.ButtonStyle.green, custom_id=f"{CUSTOM_ID_ACCEPT_PREFIX}{requester_id}"
        )
        cancel = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.red, custom_id=f"{CUSTOM_ID_CANCEL_PREFIX}{requester_id}"
        )
        view.add_item(accept)
        view.add_item(cancel)
        return view

    def _make_active_view(self, guest_id: str, host_id: str) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        for i in range(1, 6):
            button = discord.ui.Button(
                label="★" * i,
                style=discord.ButtonStyle.secondary,
                custom_id=f"{CUSTOM_ID_RATE_PREFIX}{guest_id}:{host_id}:{i}",
            )
            view.add_item(button)
        invalidate = discord.ui.Button(
            label="Invalidate",
            style=discord.ButtonStyle.red,
            custom_id=f"{CUSTOM_ID_INVALIDATE_PREFIX}{guest_id}:{host_id}",
        )
        view.add_item(invalidate)
        return view

    def _make_rating_view(self, guest_id: str, host_id: str) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        for i in range(1, 6):
            button = discord.ui.Button(
                label="★" * i,
                style=discord.ButtonStyle.secondary,
                custom_id=f"{CUSTOM_ID_RATE_PREFIX}{guest_id}:{host_id}:{i}",
            )
            view.add_item(button)
        return view

    def _make_invalidate_view(self, guest_id: str, host_id: str) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(
            label="Invalidate",
            style=discord.ButtonStyle.red,
            custom_id=f"{CUSTOM_ID_INVALIDATE_PREFIX}{guest_id}:{host_id}",
        )
        view.add_item(button)
        return view
