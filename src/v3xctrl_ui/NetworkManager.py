import logging
import socket
import threading
import time
from typing import Any, Dict

from v3xctrl_control.message import Latency
from v3xctrl_helper.exceptions import PeerRegistrationError
from v3xctrl_udp_relay.Peer import Peer

from v3xctrl_ui.helpers import get_external_ip
from v3xctrl_ui.Init import Init
from v3xctrl_ui.Settings import Settings


class NetworkManager:
    """Manages network connections, relay setup, and server communications."""

    def __init__(self, video_port: int, control_port: int, settings: Settings, handlers: Dict[str, Any]) -> None:
        self.video_port = video_port
        self.control_port = control_port
        self.settings = settings
        self.server_handlers = handlers

        # Network state
        self.video_receiver = None
        self.server = None
        self.server_error = None

        # Relay state
        self.relay_status_message = "Waiting for streamer..."
        self.relay_enable = False
        self.relay_server = None
        self.relay_port = 8888
        self.relay_id = None
        self.peer: Peer | None = None

        self._setup_relay_if_enabled()
        self._print_connection_info_if_needed()

    def setup_relay(self, relay_server: str, relay_id: str) -> None:
        """Configure relay connection parameters."""
        self.relay_enable = True
        self.relay_id = relay_id

        if relay_server and ':' in relay_server:
            host, port = relay_server.rsplit(':', 1)
            self.relay_server = host
            try:
                self.relay_port = int(port)
            except ValueError:
                logging.warning(f"Invalid port in relay_server: '{relay_server}', falling back to default {self.relay_port}")
        else:
            self.relay_server = relay_server

    def setup_ports(self) -> None:
        """Setup video and control ports in a background thread."""
        def task() -> None:
            video_address = None
            if self.relay_enable and self.relay_server and self.relay_id:
                local_bind_ports = {
                    "video": self.video_port,
                    "control": self.control_port
                }
                self.peer = Peer(self.relay_server, self.relay_port, self.relay_id)

                try:
                    addresses = self.peer.setup("viewer", local_bind_ports)
                    video_address = addresses["video"]
                except PeerRegistrationError as e:
                    self.relay_status_message = "Peer registration failed - check server and ID!"
                    logging.error(f"Peer registration failed: {e}")
                    return

            def keep_alive() -> None:
                if self.relay_enable and video_address:
                    sock = None
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        sock.bind(("0.0.0.0", self.video_port))

                        for i in range(5):
                            try:
                                sock.sendto(b'SYN', video_address)
                                time.sleep(0.1)
                            except Exception as e:
                                logging.warning(f"Poke {i+1}/5 failed: {e}")

                    except Exception as e:
                        logging.error(f"Failed to poke peer: {e}", exc_info=True)
                    finally:
                        if sock:
                            sock.close()
                        logging.info(f"Sent 'keep alive' to {video_address}")

            self.video_receiver = Init.video_receiver(self.video_port, keep_alive)

            # Set up UDP server - from this point on we can ignore
            # PeerAnnouncement messages which might be poisoning our timestamps
            try:
                self.server = Init.server(
                    self.control_port,
                    self.server_handlers.get("messages", []),
                    self.server_handlers.get("states", [])
                )
            except RuntimeError as e:
                self.server_error = str(e)
                logging.error(f"Server setup failed: {str(e)}")

            logging.info("Port setup complete.")

        threading.Thread(target=task, daemon=True).start()

    def send_latency_check(self) -> None:
        """Send a latency check message if server is available."""
        if self.server and not self.server_error:
            self.server.send(Latency())

    def get_data_queue_size(self) -> int:
        """Get the size of the outgoing data queue."""
        if self.server and not self.server_error:
            return self.server.transmitter.queue.qsize()

        return 0

    def shutdown(self) -> None:
        """Shutdown network connections."""
        if self.server:
            start = time.monotonic()
            self.server.stop()
            self.server.join()
            delta = round(time.monotonic() - start)
            logging.debug(f"Server shut down after {delta}s")

        if self.peer:
            self.peer.abort()

        if self.video_receiver:
            start = time.monotonic()
            self.video_receiver.stop()
            self.video_receiver.join()
            delta = round(time.monotonic() - start)
            logging.debug(f"Video Receiver shut down after {delta}s")

    def _setup_relay_if_enabled(self) -> None:
        """Setup relay connection if enabled in settings."""
        relay = self.settings.get("relay", {})
        if relay.get("enabled", False):
            server = relay.get("server")
            relay_id = relay.get("id")
            if server and relay_id:
                self.setup_relay(server, relay_id)

    def _print_connection_info_if_needed(self) -> None:
        """Print connection info to console if not using relay."""
        relay = self.settings.get("relay", {})
        if not relay.get("enabled", False):
            ip = get_external_ip()
            ports = self.settings.get("ports")

            print("================================")
            print(f"IP Address:   {ip}")
            print(f"Video port:   {ports['video']}")
            print(f"Control port: {ports['control']}")
            print("Make sure to forward this ports!")
            print("================================")
