# src/v3xctrl_udp_relay/Bot.py
import logging
from typing import cast
import discord
from discord.ext import commands
from v3xctrl_udp_relay.SessionStore import SessionStore

class Bot(commands.Bot):
    def __init__(self, db_path: str, token: str, command_prefix: str = '!') -> None:
        self.token = token
        self.store = SessionStore(db_path)

        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=command_prefix, intents=intents)

        self.add_command(self._requestid_command())

    def run_bot(self) -> None:
        super().run(self.token)

    async def on_ready(self) -> None:
        logging.info(f"Bot connected as {self.user}")

    def _requestid_command(self):
        @commands.command(name="requestid")
        async def requestid(ctx: commands.Context):
            bot: Bot = cast(Bot, ctx.bot)

            # If called in a guild, try to react (already awaited below)
            if ctx.guild is not None:
                try:
                    await ctx.message.add_reaction("✅")
                except discord.HTTPException:
                    pass

            user_id = str(ctx.author.id)
            display_name = str(ctx.author)

            try:
                existing = bot.store.get(user_id)
                session_id = existing or bot.store.create(user_id, display_name)

                try:
                    await ctx.author.send(f"Your session ID is: `{session_id}`")
                except discord.Forbidden:
                    await ctx.reply(
                        "I couldn't DM you. Please enable DMs from server members and try again."
                    )

            except Exception:
                # Creation failed or store raised
                try:
                    await ctx.author.send(
                        "Failed to generate a unique session ID. Try again later."
                    )
                except discord.Forbidden:
                    await ctx.reply(
                        "I couldn't DM you. Please enable DMs from server members and try again."
                    )

        return requestid
