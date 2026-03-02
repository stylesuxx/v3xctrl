import json
import logging
import socket
from typing import Any


class RelayClient:
    COMMAND_SOCKET_TEMPLATE = "/tmp/udp_relay_command_{port}.sock"

    def __init__(self, port: int = 8888) -> None:
        self.socket_path = self.COMMAND_SOCKET_TEMPLATE.format(port=port)
        self.timeout = 5.0

    def get_stats(self) -> dict[str, Any]:
        return self.send_command(b"stats")

    def send_command(self, command: bytes) -> dict[str, Any]:
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
            sock.send(command)
            data = sock.recv(4096)

            return json.loads(data.decode('utf-8'))

        except Exception as e:
            logging.error(f"Failed to send command {command}: {e}")
            raise

        finally:
            if sock:
                try:
                    sock.close()

                except Exception:
                    # Ignore close errors
                    pass
