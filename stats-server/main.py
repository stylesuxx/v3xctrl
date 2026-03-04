import argparse
import secrets

from flask import Flask

from auth import auth_blueprint
from stats import create_stats_blueprint, RelayClient


def create_app(
    relay_ports: list[int],
    users_file: str,
    secret_key: str,
) -> Flask:
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = secret_key
    app.config['USERS_FILE'] = users_file

    relay_clients = {port: RelayClient(port) for port in relay_ports}

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(create_stats_blueprint(relay_clients))

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Stats web interface for UDP relay servers.")
    parser.add_argument(
        '--relay-port',
        type=int,
        action='append',
        required=True,
        dest='relay_ports',
        help='Relay server port (can be specified multiple times)',
    )
    parser.add_argument(
        '--users-file',
        required=True,
        help='Path to users.json file with password hashes',
    )
    parser.add_argument(
        '--secret-key',
        default=None,
        help='Secret key for session signing (default: random per restart)',
    )
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', default=8080, type=int, help='Port to listen on')
    args = parser.parse_args()

    secret_key = args.secret_key or secrets.token_hex(32)

    app = create_app(
        relay_ports=args.relay_ports,
        users_file=args.users_file,
        secret_key=secret_key,
    )
    app.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
