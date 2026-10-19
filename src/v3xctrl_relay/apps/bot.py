import argparse
import logging
import sys

from v3xctrl_relay import config
from v3xctrl_relay.discord_bot import Bot

DEFAULT_LOG_LEVEL = "ERROR"
DEFAULT_DB_PATH = "relay.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Discord relay bot.")
    parser.add_argument("token", nargs="?", help="Discord bot token")
    parser.add_argument("channel_id", nargs="?", type=int, help="Discord channel ID where bot commands can be used")
    parser.add_argument("--testdrive-channel-id", type=int, help="Discord channel ID for test drive requests")
    parser.add_argument(
        "--db", "--db-path", dest="db_path", help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--log", help=f"Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: {DEFAULT_LOG_LEVEL})"
    )
    parser.add_argument("--config", default=config.DEFAULT_CONFIG_PATH, help="Path to the configuration file")

    return parser.parse_args()


def resolve_settings(args: argparse.Namespace) -> tuple[str, int, int | None, str, str]:
    loaded = config.load(args.config)

    bot = config.get_section(loaded, "bot")
    paths = config.get_section(loaded, "paths")

    token = config.require(args.token or bot.get("token"), "token", "the token argument")
    channel_id = config.require(args.channel_id or bot.get("channel_id"), "channel_id", "the channel_id argument")
    testdrive_channel_id = args.testdrive_channel_id or bot.get("testdrive_channel_id")
    log_level = args.log or bot.get("log") or DEFAULT_LOG_LEVEL
    db_path = args.db_path or paths.get("database") or DEFAULT_DB_PATH

    return (token, channel_id, testdrive_channel_id, log_level, db_path)


def main() -> None:
    args = parse_args()

    try:
        token, channel_id, testdrive_channel_id, log_level, db_path = resolve_settings(args)

    except config.ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    level = getattr(logging, log_level.upper(), None)

    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

    bot = Bot(db_path, token, channel_id, testdrive_channel_id=testdrive_channel_id)
    bot.run_bot()


if __name__ == "__main__":
    main()
