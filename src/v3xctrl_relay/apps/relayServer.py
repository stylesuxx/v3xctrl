import argparse
import logging
import signal
import sys
from types import FrameType

from v3xctrl_relay import config
from v3xctrl_relay.RelayServer import RelayServer

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8888
DEFAULT_LOG_LEVEL = "ERROR"
DEFAULT_DB_PATH = "relay.db"
DEFAULT_RUNTIME_DIRECTORY = RelayServer.COMMAND_SOCKET_DIRECTORY


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a UDP relay server.")
    parser.add_argument("ip", nargs="?", help="IP address to advertise to peers")
    parser.add_argument("--port", type=int, help=f"UDP port to bind to (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--log", help=f"Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: {DEFAULT_LOG_LEVEL})"
    )
    parser.add_argument(
        "--db", "--db-path", dest="db_path", help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--runtime-dir",
        dest="runtime_directory",
        help=f"Directory holding the command socket (default: {DEFAULT_RUNTIME_DIRECTORY})",
    )
    parser.add_argument("--instance", help="Name of the [relay.<instance>] table to read from the configuration file")
    parser.add_argument("--config", default=config.DEFAULT_CONFIG_PATH, help="Path to the configuration file")

    return parser.parse_args()


def resolve_settings(args: argparse.Namespace) -> tuple[str, int, str, str, str]:
    loaded = config.load(args.config)

    relay = config.get_section(loaded, "relay", args.instance) if args.instance else {}
    paths = config.get_section(loaded, "paths")

    if args.instance and not relay:
        raise config.ConfigError(f"{args.config}: no [relay.{args.instance}] table")

    ip = config.require(args.ip or relay.get("bind_ip"), "bind_ip", "the ip argument")
    port = args.port or relay.get("port") or DEFAULT_PORT
    log_level = args.log or relay.get("log") or DEFAULT_LOG_LEVEL
    db_path = args.db_path or paths.get("database") or DEFAULT_DB_PATH
    runtime_directory = args.runtime_directory or paths.get("runtime_directory") or DEFAULT_RUNTIME_DIRECTORY

    return (ip, port, log_level, db_path, runtime_directory)


def main() -> None:
    args = parse_args()

    try:
        ip, port, log_level, db_path, runtime_directory = resolve_settings(args)
    except config.ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    level = getattr(logging, log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

    server = RelayServer(ip, port, db_path, command_socket_directory=runtime_directory)

    def shutdown(signum: int, frame: FrameType | None) -> None:
        logger.info("Shutting down RelayServer...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    server.start()
    server.join()


if __name__ == "__main__":
    main()
