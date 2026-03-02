import argparse
import logging

from v3xctrl_udp_relay.discord_bot import Bot
from v3xctrl_udp_relay.discord_bot.RelayClient import RelayClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Discord relay bot.")
    parser.add_argument("token", help="Discord bot token")
    parser.add_argument("channel_id", type=int,
                        help="Discord channel ID where bot commands can be used (required)")
    parser.add_argument("--testdrive-channel-id", type=int, default=None,
                        help="Discord channel ID for test drive requests (optional)")
    parser.add_argument("--db", "--db-path", dest="db_path", default="relay.db",
                        help="Path to SQLite database (default: relay.db)")
    parser.add_argument("--relay-port", type=int, default=8888,
                        help="Port of the relay server to connect to for stats (default: 8888)")
    parser.add_argument("--log", default="ERROR",
                        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR")
    args = parser.parse_args()

    level_name = args.log.upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    relay_client = RelayClient(port=args.relay_port)
    bot = Bot(args.db_path, args.token, args.channel_id,
              testdrive_channel_id=args.testdrive_channel_id,
              relay_client=relay_client)
    bot.run_bot()


if __name__ == "__main__":
    main()
