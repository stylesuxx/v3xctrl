import io
import json
import logging
from typing import Any

import discord
from discord.ext import commands

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.discord_bot.RelayClient import RelayClient


class Bot(commands.Bot):
    def __init__(
        self,
        db_path: str,
        token: str,
        relay_client: RelayClient | None = None,
        command_prefix: str = '!'
    ) -> None:
        self.token = token
        self.store = SessionStore(db_path)
        self.relay_client = relay_client or RelayClient()

        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix=command_prefix, intents=intents)

        self.add_command(self._requestid_command())
        self.add_command(self._stats_command())
        self.add_command(self._renewid_command())

    def run_bot(self) -> None:
        super().run(self.token)

    async def on_ready(self) -> None:
        logging.info(f"Bot connected as {self.user}")

    def _has_role(self, member: discord.Member, role_names: list[str]) -> bool:
        """Check if member has any of the specified roles or manage messages permission"""
        if member.guild_permissions.manage_messages:
            return True

        role_names_lower = [name.lower() for name in role_names]
        return any(role.name.lower() in role_names_lower for role in member.roles)

    def _get_relay_stats(self) -> dict[str, Any]:
        """Get stats from UDP relay via RelayClient"""
        return self.relay_client.get_stats()

    def _format_stats_message(self, stats: dict[str, Any]) -> str:
        """Format stats into Discord message"""
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

    async def handle_stats_command(self, ctx: commands.Context[Any]) -> None:
        """Extracted stats logic - easily testable"""
        if ctx.guild is None:
            await ctx.reply("This command can only be used in a server.")
            return

        if not isinstance(ctx.author, discord.Member):
            try:
                await ctx.message.add_reaction("❌")

            except discord.HTTPException:
                pass

            return

        # Must have stats role
        if not self._has_role(ctx.author, ['stats']):
            try:
                await ctx.message.add_reaction("❌")

            except discord.HTTPException:
                pass

            return

        try:
            relay_stats = self._get_relay_stats()
            formatted_stats = self._format_stats_message(relay_stats)

            if len(formatted_stats) > 2000:
                stats_file = io.BytesIO(json.dumps(relay_stats, indent=2).encode('utf-8'))
                file = discord.File(stats_file, filename="relay_stats.json")
                await ctx.author.send("Stats too long for message, sending as file:", file=file)

            else:
                await ctx.author.send(formatted_stats)

            try:
                await ctx.message.add_reaction("✅")

            except discord.HTTPException:
                pass

        except discord.Forbidden:
            await ctx.reply("I couldn't DM you the stats. Please enable DMs from server members and try again.")

            try:
                await ctx.message.add_reaction("❌")

            except discord.HTTPException:
                pass

        except Exception as e:
            logging.error(f"Stats command failed: {e}")
            await ctx.reply("Failed to retrieve relay statistics. Check if the relay server is running.")

            try:
                await ctx.message.add_reaction("❌")

            except discord.HTTPException:
                pass

    async def handle_requestid_command(self, ctx: commands.Context[Any]) -> None:
        """Extracted requestid logic - easily testable"""
        if ctx.guild is not None:
            try:
                await ctx.message.add_reaction("✅")

            except discord.HTTPException:
                pass

            logging.info(f"!requestid called by {ctx.author} in server, responding via DM.")

        user_id = str(ctx.author.id)
        username = str(ctx.author)

        session_id = self.store.get(user_id)
        if session_id:
            logging.info(f"Returning existing session ID for {username}")

        else:
            try:
                session_id = self.store.create(user_id, username)

            except RuntimeError as e:
                logging.error(f"ID generation failed for {username}: {e}")
                await ctx.author.send("Failed to generate a unique session ID. Try again later.")
                return

        try:
            await ctx.author.send(f"Your session ID is: `{session_id}`")

        except discord.Forbidden:
            await ctx.reply("I couldn't DM you. Please enable DMs from server members and try again.")

    async def handle_renewid_command(self, ctx: commands.Context[Any]) -> None:
        """Extracted renewid logic - easily testable"""
        if ctx.guild is not None:
            try:
                await ctx.message.add_reaction("✅")
            except discord.HTTPException:
                pass

            logging.info(f"!renewid called by {ctx.author} in server, responding via DM.")

        user_id = str(ctx.author.id)
        username = str(ctx.author)

        existing_session = self.store.get(user_id)

        try:
            if existing_session:
                session_id = self.store.update(user_id, username)
                logging.info(f"Renewed session ID for {username}")
            else:
                session_id = self.store.create(user_id, username)
                logging.info(f"Created new session ID for {username}")

            await ctx.author.send(f"Your session ID is: `{session_id}`")

        except RuntimeError as e:
            logging.error(f"ID generation failed for {username}: {e}")
            await ctx.author.send("Failed to generate a unique session ID. Try again later.")
        except discord.Forbidden:
            await ctx.reply("I couldn't DM you. Please enable DMs from server members and try again.")

    def _stats_command(self) -> commands.Command[Any, Any, Any]:
        @commands.command(name="stats")
        async def stats(ctx: commands.Context[Any]) -> None:
            await self.handle_stats_command(ctx)

        return stats

    def _requestid_command(self) -> commands.Command[Any, Any, Any]:
        @commands.command(name="requestid")
        async def requestid(ctx: commands.Context[Any]) -> None:
            await self.handle_requestid_command(ctx)

        return requestid

    def _renewid_command(self) -> commands.Command[Any, Any, Any]:
        @commands.command(name="renewid")
        async def renewid(ctx: commands.Context[Any]) -> None:
            await self.handle_renewid_command(ctx)

        return renewid
