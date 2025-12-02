import json
import logging
import os
import socket
import threading
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from v3xctrl_gst.Streamer import Streamer


class ControlServer:
    """Unix socket-based control server for runtime pipeline control."""

    def __init__(self, streamer: 'Streamer', socket_path: str = '/tmp/v3xctrl.sock') -> None:
        """
        Initialize the control server.

        Args:
            streamer: Streamer instance to control
            socket_path: Path to Unix socket file
        """
        self.streamer = streamer
        self.socket_path = socket_path

        self.server_socket: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

    def start(self) -> None:
        """Start the control server in a separate thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()

        logging.info(f"Control server started on {self.socket_path}")

    def stop(self) -> None:
        """Stop the control server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except Exception:
            pass

    def _run_server(self) -> None:
        """Main server loop."""

        # Remove existing socket if any
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except Exception as e:
            logging.error(f"Failed to remove existing socket: {e}")
            return

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            self.server_socket.bind(self.socket_path)
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)

            # Anyone has access
            os.chmod(self.socket_path, 0o666)

            while self.running:
                try:
                    client_socket, _ = self.server_socket.accept()
                    logging.info("Client connected")

                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket,),
                        daemon=True
                    )
                    client_thread.start()

                except socket.timeout:
                    continue

                except Exception as e:
                    if self.running:
                        logging.error(f"Server error: {e}")

        finally:
            if self.server_socket:
                self.server_socket.close()

            try:
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
            except Exception:
                pass

    def _handle_client(self, client_socket: socket.socket) -> None:
        """
        Handle a client connection.

        Args:
            client_socket: Connected client socket
        """
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break

                try:
                    command = json.loads(data.decode('utf-8'))
                    response = self._execute_command(command)

                except json.JSONDecodeError as e:
                    response = {'status': 'error', 'message': f'Invalid JSON: {e}'}

                except Exception as e:
                    response = {'status': 'error', 'message': str(e)}

                client_socket.sendall(json.dumps(response).encode('utf-8') + b'\n')

        except Exception as e:
            logging.error(f"Client handler error: {e}")
        finally:
            client_socket.close()

    def _execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a control command.

        Args:
            command: Command dictionary with 'action' and parameters

        Returns:
            Response dictionary with status and result
        """
        action = command.get('action')
        if not action:
            return {'status': 'error', 'message': 'Missing action parameter'}

        if action == 'stop':
            self.streamer.stop()
            return {'status': 'success', 'message': 'Pipeline stopped'}

        element = command.get('element')
        if not element:
            return {'status': 'error', 'message': 'Missing element parameter'}

        if action == 'list':
            properties = self.streamer.list_properties(element)
            return {
                'status': 'success' if properties is not None else 'error',
                'element': element,
                'properties': self._serialize_properties(properties)
            }

        if action == 'update':
            properties = command.get('properties')
            if not properties:
                return {'status': 'error', 'message': 'Missing properties parameter'}

            success = self.streamer.update_properties(element, properties)
            return {
                'status': 'success' if success else 'error',
                'element': element,
                'properties': properties
            }

        property_name = command.get('property')
        if not property_name:
            return {'status': 'error', 'message': 'Missing property parameters'}

        if action == 'get':
            value = self.streamer.get_property(element, property_name)
            return {
                'status': 'success' if value is not None else 'error',
                'element': element,
                'property': property_name,
                'value': self._serialize_value(value)
            }

        if action == 'set':
            value = command.get('value')
            if value is None:
                return {'status': 'error', 'message': 'Missing value'}

            success = self.streamer.set_property(element, property_name, value)
            return {
                'status': 'success' if success else 'error',
                'element': element,
                'property': property_name,
                'value': value
            }

        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def _serialize_value(self, value: Any) -> Any:
        """
        Convert a value to JSON-serializable format.

        Args:
            value: Value to serialize

        Returns:
            JSON-serializable representation of the value
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]

        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}

        else:
            # For GStreamer objects and other non-serializable types
            return str(value)

    def _serialize_properties(self, properties: Any) -> Any:
        """
        Convert properties dict to JSON-serializable format.

        Args:
            properties: Properties dictionary or object

        Returns:
            JSON-serializable representation
        """
        if properties is None:
            return None

        if isinstance(properties, dict):
            return {k: self._serialize_value(v) for k, v in properties.items()}
        else:
            # If properties is not a dict, convert to string
            return str(properties)
