import argparse
import secrets
import sys

import config
from auth import auth_blueprint
from flask import Flask
from stats import RelayClient, create_stats_blueprint

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080


def create_app(
    relay_ports: list[int],
    users_file: str,
    secret_key: str,
    command_socket_directory: str | None = None,
) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = secret_key
    app.config["USERS_FILE"] = users_file

    relay_clients = {port: RelayClient(port, command_socket_directory) for port in relay_ports}

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(create_stats_blueprint(relay_clients))

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stats web interface for UDP relay servers.")
    parser.add_argument(
        "--relay-port",
        type=int,
        action="append",
        dest="relay_ports",
        help="Relay server port (can be specified multiple times)",
    )
    parser.add_argument("--users-file", help="Path to users.json file with password hashes")
    parser.add_argument(
        "--secret-key",
        default=None,
        help="Secret key for session signing (default: random per restart)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind to (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--runtime-dir",
        dest="runtime_directory",
        help=f"Directory holding the relay command sockets (default: {RelayClient.COMMAND_SOCKET_DIRECTORY})",
    )
    parser.add_argument("--config", default=config.DEFAULT_CONFIG_PATH, help="Path to the configuration file")

    return parser.parse_args()


def resolve_settings(args: argparse.Namespace) -> tuple[list[int], str, str, int, str]:
    """
    Combine command line arguments with the configuration file.

    A command line argument always wins, then the configuration file, then the
    built-in default.
    """
    loaded = config.load(args.config)

    stats = config.get_section(loaded, "stats")
    paths = config.get_section(loaded, "paths")

    relay_ports = args.relay_ports or config.get_relay_ports(stats)
    if not relay_ports:
        raise config.ConfigError("no relay ports: pass --relay-port or set stats.relay_ports in the configuration file")

    users_file = args.users_file or paths.get("users_file")
    if not users_file:
        raise config.ConfigError("users_file is not set: pass --users-file or set it in the configuration file")

    secret_key = args.secret_key or stats.get("secret_key") or secrets.token_hex(32)
    port = args.port or stats.get("port") or DEFAULT_PORT
    runtime_directory = args.runtime_directory or paths.get("runtime_directory") or RelayClient.COMMAND_SOCKET_DIRECTORY

    return (relay_ports, users_file, secret_key, port, runtime_directory)


def main() -> None:
    args = parse_args()

    try:
        relay_ports, users_file, secret_key, port, runtime_directory = resolve_settings(args)
    except config.ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    app = create_app(
        relay_ports=relay_ports,
        users_file=users_file,
        secret_key=secret_key,
        command_socket_directory=runtime_directory,
    )
    app.run(host=args.host, port=port)


if __name__ == "__main__":
    main()
