import logging
from typing import Any

import discord
from discord.ext import commands

from v3xctrl_udp_relay.SessionStore import SessionStore


class Bot(commands.Bot):
    def __init__(
        self,
        db_path: str,
        token: str,
        command_prefix: str = '!'
    ) -> None:
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

    def _requestid_command(self) -> Any | None:
        @commands.command(name="requestid")
        async def requestid(ctx: commands.Context[Any]) -> None:
            bot: Bot = ctx.bot

            if ctx.guild is not None:
                try:
                    await ctx.message.add_reaction("✅")
                except discord.HTTPException:
                    pass
                logging.info(f"!requestid called by {ctx.author} in server, responding via DM.")

            user_id = str(ctx.author.id)
            username = str(ctx.author)

            session_id = bot.store.get(user_id)
            if session_id:
                logging.info(f"Returning existing session ID for {username}")
            else:
                try:
                    session_id = bot.store.create(user_id, username)
                except RuntimeError as e:
                    logging.error(f"ID generation failed for {username}: {e}")
                    await ctx.author.send("Failed to generate a unique session ID. Try again later.")
                    return

            try:
                await ctx.author.send(f"Your session ID is: `{session_id}`")
            except discord.Forbidden:
                await ctx.reply("I couldn't DM you. Please enable DMs from server members and try again.")

        return requestid
