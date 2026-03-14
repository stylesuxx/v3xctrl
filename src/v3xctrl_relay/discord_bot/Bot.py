import logging

import discord
from discord import app_commands

from v3xctrl_relay.discord_bot.testdrive import TestdriveHandler
from v3xctrl_relay.SessionStore import SessionStore


class Bot(discord.Client):
    def __init__(
        self,
        db_path: str,
        token: str,
        channel_id: int,
        testdrive_channel_id: int | None = None,
    ) -> None:
        self.token = token
        self.store = SessionStore(db_path)
        self.channel_id = channel_id
        self.testdrive_channel_id = testdrive_channel_id

        self.testdrive_handler: TestdriveHandler | None = None
        if testdrive_channel_id is not None:
            self.testdrive_handler = TestdriveHandler(self.store, testdrive_channel_id)

        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content for auto-deletion

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self._register_commands()

    def _register_commands(self) -> None:
        @self.tree.command(name="requestid", description="Request your unique session ID via DM")
        async def requestid_cmd(interaction: discord.Interaction) -> None:
            await self.handle_requestid_command(interaction)

        @self.tree.command(name="renewid", description="Renew your session ID via DM")
        async def renewid_cmd(interaction: discord.Interaction) -> None:
            await self.handle_renewid_command(interaction)

    async def setup_hook(self) -> None:
        await self.tree.sync()

    def run_bot(self) -> None:
        super().run(self.token)

    async def on_ready(self) -> None:
        logging.info(f"Bot connected as {self.user}")
        await self._announce_presence()
        await self._announce_testdrive()

    async def on_message(self, message: discord.Message) -> None:
        """Delete any non-bot messages in the designated channels"""
        monitored_channels = {self.channel_id}
        if self.testdrive_channel_id:
            monitored_channels.add(self.testdrive_channel_id)

        if message.channel.id not in monitored_channels:
            return

        # Don't delete bot's own messages
        if message.author == self.user:
            return

        try:
            await message.delete()
        except discord.Forbidden:
            logging.error(f"Cannot delete messages in channel {message.channel.id} - missing permissions")
        except Exception as e:
            logging.error(f"Failed to delete message in channel {message.channel.id}: {e}")

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Route component interactions (buttons) to testdrive handler"""
        if interaction.type == discord.InteractionType.application_command:
            return

        if interaction.type == discord.InteractionType.component:
            if self.testdrive_handler:
                await self.testdrive_handler.handle_interaction(interaction)

    async def _announce_presence(self) -> None:
        announcement = (
            "## v3xctrl Relay Bot is now online!\n\n"
            "I use slash commands **in this channel only**. Type `/` to see available commands:\n"
            "• `/requestid` - Get your unique session ID for connecting\n"
            "• `/renewid` - Generate a new session ID\n\n"
            "All responses are sent via DM for privacy.\n\n"
            "## CAUTION!\n"
            "**Do not share your session ID** with untrusted users, they will have access to your streamer.\n\n"
            "Messages will be auto-deleted in this channel, only interactions with me are allowed!"
        )

        channel = self.get_channel(self.channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            try:
                await channel.send(announcement)
            except discord.Forbidden:
                logging.error(f"Cannot send announcement to channel {self.channel_id} - missing permissions")
            except Exception as e:
                logging.error(f"Failed to announce in channel {self.channel_id}: {e}")
        else:
            logging.error(f"Announcement channel {self.channel_id} not found or not a text channel")

    async def _announce_testdrive(self) -> None:
        if not self.testdrive_handler or not self.testdrive_channel_id:
            return

        channel = self.get_channel(self.testdrive_channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            await self.testdrive_handler.post_persistent_message(channel)
        else:
            logging.error(
                f"Testdrive channel {self.testdrive_channel_id} not found or not a text channel"
            )

    def _is_correct_channel(self, interaction: discord.Interaction) -> bool:
        return interaction.channel_id == self.channel_id

    async def handle_requestid_command(self, interaction: discord.Interaction) -> None:
        # Silently ignore commands from other channels
        if not self._is_correct_channel(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        username = str(interaction.user)

        result = self.store.get(user_id)
        if result:
            session_id, spectator_id = result
            logging.info(f"Returning existing session ID for {username}")
        else:
            try:
                session_id, spectator_id = self.store.create(user_id, username)

            except RuntimeError as e:
                logging.error(f"ID generation failed for {username}: {e}")
                await interaction.followup.send("Failed to generate a unique session ID. Try again later.", ephemeral=True)
                return

        try:
            await interaction.user.send(
                f"Your session ID is: `{session_id}`\n"
                f"Your spectator ID is: `{spectator_id}`\n\n"
                f"**Session ID**: Use this to stream or view as the main participant.\n"
                f"**Spectator ID**: Share this with others to let them watch your session without giving them control.\n\n"
                "**CAUTION**: Do not share your session ID with untrusted users!"
            )
            await interaction.followup.send("Session ID sent via DM!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("I couldn't DM you. Please enable DMs from server members and try again.", ephemeral=True)

    async def handle_renewid_command(self, interaction: discord.Interaction) -> None:
        # Silently ignore commands from other channels
        if not self._is_correct_channel(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        username = str(interaction.user)

        existing_session = self.store.get(user_id)

        try:
            if existing_session:
                session_id, spectator_id = self.store.update(user_id, username)
                logging.info(f"Renewed session ID for {username}")
            else:
                session_id, spectator_id = self.store.create(user_id, username)
                logging.info(f"Created new session ID for {username}")

            await interaction.user.send(
                f"Your session ID is: `{session_id}`\n"
                f"Your spectator ID is: `{spectator_id}`\n\n"
                f"**Session ID**: Use this to stream or view as the main participant.\n"
                f"**Spectator ID**: Share this with others to let them watch your session without giving them control.\n\n"
                "**CAUTION**: Do not share your session ID with untrusted users!"
            )
            await interaction.followup.send("Session ID sent via DM!", ephemeral=True)

        except RuntimeError as e:
            logging.error(f"ID generation failed for {username}: {e}")
            await interaction.followup.send("Failed to generate a unique session ID. Try again later.", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("I couldn't DM you. Please enable DMs from server members and try again.", ephemeral=True)
