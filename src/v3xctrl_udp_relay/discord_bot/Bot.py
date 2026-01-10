import io
import json
import logging
from typing import Any

import discord
from discord import app_commands

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.discord_bot.RelayClient import RelayClient


class Bot(discord.Client):
    def __init__(
        self,
        db_path: str,
        token: str,
        channel_id: int,
        relay_client: RelayClient | None = None
    ) -> None:
        self.token = token
        self.store = SessionStore(db_path)
        self.relay_client = relay_client or RelayClient()
        self.channel_id = channel_id

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

        @self.tree.command(name="stats", description="Get relay server statistics via DM")
        async def stats_cmd(interaction: discord.Interaction) -> None:
            await self.handle_stats_command(interaction)

    async def setup_hook(self) -> None:
        await self.tree.sync()

    def run_bot(self) -> None:
        super().run(self.token)

    async def on_ready(self) -> None:
        logging.info(f"Bot connected as {self.user}")
        await self._announce_presence()

    async def on_message(self, message: discord.Message) -> None:
        """Delete any non-bot messages in the designated channel"""
        # Only monitor the designated channel
        if message.channel.id != self.channel_id:
            return

        # Don't delete bot's own messages
        if message.author == self.user:
            return

        try:
            await message.delete()
        except discord.Forbidden:
            logging.error(f"Cannot delete messages in channel {self.channel_id} - missing permissions")
        except Exception as e:
            logging.error(f"Failed to delete message in channel {self.channel_id}: {e}")

    async def _announce_presence(self) -> None:
        announcement = (
            "## v3xctrl Relay Bot is now online!\n\n"
            "I use slash commands **in this channel only**. Type `/` to see available commands:\n"
            "• `/requestid` - Get your unique session ID for connecting\n"
            "• `/renewid` - Generate a new session ID\n"
            "• `/stats` - View relay server statistics (requires 'stats' role)\n\n"
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

    def _is_correct_channel(self, interaction: discord.Interaction) -> bool:
        return interaction.channel_id == self.channel_id

    def _has_role(self, member: discord.Member, role_names: list[str]) -> bool:
        if member.guild_permissions.manage_messages:
            return True

        role_names_lower = [name.lower() for name in role_names]
        return any(role.name.lower() in role_names_lower for role in member.roles)

    def _get_relay_stats(self) -> dict[str, Any]:
        return self.relay_client.get_stats()

    def _format_stats_message(self, stats: dict[str, Any]) -> str:
        if not stats:
            return "No active sessions."

        message_parts = [f"**Active Sessions: {len(stats)}**\n"]

        for session_id, session_data in stats.items():
            created_at = session_data.get('created_at', 0)
            mappings = session_data.get('mappings', [])

            timestamp = f"<t:{int(created_at)}:R>"

            message_parts.append(f"**Session ID:** `{session_id}`")
            message_parts.append(f"**Created:** {timestamp}")
            message_parts.append("")

            if mappings:
                streamers = [m for m in mappings if m['role'] == 'STREAMER']
                viewers = [m for m in mappings if m['role'] == 'VIEWER']

                if streamers:
                    timeout = 0
                    for mapping in streamers:
                        if mapping['timeout_in_sec'] > timeout:
                            timeout = mapping['timeout_in_sec']

                    message_parts.append(f"**STREAMER (Timeout in {timeout}sec):**")
                    for mapping in streamers:
                        message_parts.append(f"    • {mapping['address']} ({mapping['port_type']})")
                    message_parts.append("")

                if viewers:
                    timeout = 0
                    for mapping in viewers:
                        if mapping['timeout_in_sec'] > timeout:
                            timeout = mapping['timeout_in_sec']

                    message_parts.append(f"**VIEWER (Timeout in {timeout}sec):**")
                    for mapping in viewers:
                        message_parts.append(f"    • {mapping['address']} ({mapping['port_type']})")
                    message_parts.append("")

            else:
                message_parts.append("  *No active mappings*")
                message_parts.append("")

            message_parts.append("─" * 50)
            message_parts.append("")

        return "\n".join(message_parts)

    async def handle_stats_command(self, interaction: discord.Interaction) -> None:
        # Silently ignore commands from other channels
        if not self._is_correct_channel(interaction):
            return

        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command is only available to server members.", ephemeral=True)
            return

        if not self._has_role(interaction.user, ['stats']):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return

        try:
            relay_stats = self._get_relay_stats()
            formatted_stats = self._format_stats_message(relay_stats)

            await interaction.response.defer(ephemeral=True)

            if len(formatted_stats) > 2000:
                stats_file = io.BytesIO(json.dumps(relay_stats, indent=2).encode('utf-8'))
                file = discord.File(stats_file, filename="relay_stats.json")
                await interaction.user.send("Stats too long for message, sending as file:", file=file)

            else:
                await interaction.user.send(formatted_stats)

            await interaction.followup.send("Stats sent via DM!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "I couldn't DM you the stats. Please enable DMs from server members and try again.",
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Stats command failed: {e}")
            await interaction.followup.send(
                "Failed to retrieve relay statistics. Check if the relay server is running.",
                ephemeral=True
            )

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
