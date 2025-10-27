import socket
import json
from typing import Dict, Any


class ControlClient:
    """Client to control a running Streamer instance."""

    def __init__(self, socket_path: str = '/tmp/v3xctrl.sock') -> None:
        """
        Initialize the client.

        Args:
            socket_path: Path to Unix socket file
        """
        self.socket_path = socket_path

    def set_property(self, element: str, property_name: str, value: Any) -> Dict[str, Any]:
        """Set a property on an element."""
        return self._send_command({
            'action': 'set',
            'element': element,
            'property': property_name,
            'value': value
        })

    def get_property(self, element: str, property_name: str) -> Dict[str, Any]:
        """Get a property from an element."""
        return self._send_command({
            'action': 'get',
            'element': element,
            'property': property_name
        })

    def list_properties(self, element: str) -> Dict[str, Any]:
        """List all properties of an element."""
        return self._send_command({
            'action': 'list',
            'element': element
        })

    def update_properties(self, element: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Update multiple properties at once."""
        return self._send_command({
            'action': 'update',
            'element': element,
            'properties': properties
        })

    def stop_pipeline(self) -> Dict[str, Any]:
        return self._send_command({'action': 'stop'})

    def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a command to the control server.

        Args:
            command: Command dictionary

        Returns:
            Response dictionary
        """
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)

            sock.sendall(json.dumps(command).encode('utf-8'))
            response = sock.recv(4096).decode('utf-8')
            sock.close()

            return json.loads(response)

        except Exception as e:
            return {'status': 'error', 'message': str(e)}
