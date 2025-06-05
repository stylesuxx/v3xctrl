import argparse
import logging

from v3xctrl_udp_relay.Bot import Bot


def main():
    parser = argparse.ArgumentParser(description="Run the Discord relay bot.")
    parser.add_argument('token', help='Discord bot token')
    parser.add_argument('--db', '--db-path', dest='db_path', default='relay.db',
                        help='Path to SQLite database (default: relay.db)')
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

    bot = Bot(args.db_path, args.token)
    bot.run_bot()


if __name__ == "__main__":
    main()
