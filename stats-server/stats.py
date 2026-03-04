import json
import logging
import socket
from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, session, url_for

from auth import login_required


class RelayClient:
    COMMAND_SOCKET_TEMPLATE = "/tmp/udp_relay_command_{port}.sock"

    def __init__(self, port: int) -> None:
        self.port = port
        self.socket_path = self.COMMAND_SOCKET_TEMPLATE.format(port=port)
        self.timeout = 5.0

    def get_stats(self) -> dict[str, Any]:
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
            sock.send(b"stats")
            data = sock.recv(65536)
            return json.loads(data.decode('utf-8'))
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass


def create_stats_blueprint(relay_clients: dict[int, RelayClient]) -> Blueprint:
    stats_blueprint = Blueprint('stats', __name__)

    @stats_blueprint.route('/')
    @login_required
    def dashboard() -> str:
        return render_template(
            'dashboard.html',
            relay_ports=sorted(relay_clients.keys()),
            username=session['username'],
        )

    @stats_blueprint.route('/api/stats')
    @login_required
    def api_stats() -> tuple[Any, int]:
        relays: dict[str, dict[str, Any]] = {}

        for port, client in sorted(relay_clients.items()):
            try:
                sessions = client.get_stats()
                relays[str(port)] = {
                    'status': 'ok',
                    'sessions': sessions,
                }
            except Exception as e:
                logging.warning(f"Failed to get stats from relay on port {port}: {e}")
                relays[str(port)] = {
                    'status': 'error',
                    'error': str(e),
                }

        return jsonify({'relays': relays}), 200

    return stats_blueprint
