import logging
import socket
import threading
import time
from typing import Any, Dict, Optional

from v3xctrl_control import Server
from v3xctrl_control.message import Latency, Message
from v3xctrl_control.State import State
from v3xctrl_helper.exceptions import PeerRegistrationError
from v3xctrl_udp_relay.Peer import Peer

from v3xctrl_ui.utils.helpers import get_external_ip
from v3xctrl_ui.utils.Settings import Settings
from v3xctrl_ui.network.VideoReceiverPyAV import VideoReceiverPyAV as VideoReceiver


class NetworkController:
    """Manages network connections, relay setup, and server communications."""

    def __init__(self, settings: Settings, handlers: Dict[str, Any]) -> None:
        self.settings = settings
        self.server_handlers = handlers

        ports = self.settings.get("ports", {})
        self.video_port = ports.get("video")
        self.control_port = ports.get("control")

        # Network state
        self.video_receiver = None
        self.server: Optional[Server] = None
        self.server_error = None

        # Relay state
        self.relay_status_message = "Waiting for streamer..."
        self.relay_enable = False
        self.relay_server = None
        self.relay_port = 8888
        self.relay_id = None
        self.peer: Optional[Peer] = None

        self._setup_relay_if_enabled()
        self._print_connection_info_if_needed()

    def setup_relay(self, relay_server: str, relay_id: str) -> None:
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
        threading.Thread(target=self._setup_ports_task, daemon=True).start()

    def send_latency_check(self) -> None:
        if self.server and not self.server_error:
            self.server.send(Latency())

    def get_data_queue_size(self) -> int:
        if self.server and not self.server_error:
            return self.server.transmitter.queue.qsize()

        return 0

    def shutdown(self) -> None:
        if self.server:
            start = time.monotonic()
            self.server.stop()
            self.server.join()
            delta = round(time.monotonic() - start)
            logging.debug(f"Server shut down after {delta}s")

        if self.peer:
            start = time.monotonic()
            self.peer.abort()
            delta = round(time.monotonic() - start)
            logging.debug(f"Peer aborted after {delta}s")

        if self.video_receiver:
            start = time.monotonic()
            self.video_receiver.stop()
            self.video_receiver.join()
            delta = round(time.monotonic() - start)
            logging.debug(f"Video Receiver shut down after {delta}s")

    def update_ttl(self, ttl_ms: int) -> None:
        if self.server:
            self.server.update_ttl(ttl_ms)

    def _setup_relay_if_enabled(self) -> None:
        relay = self.settings.get("relay", {})
        if relay.get("enabled", False):
            server = relay.get("server")
            relay_id = relay.get("id")
            if server and relay_id:
                self.setup_relay(server, relay_id)

    def _print_connection_info_if_needed(self) -> None:
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

    def _create_server(
        self,
        port: int,
        message_handlers: list,
        state_handlers: list,
        udp_ttl_ms: int
    ) -> Server:
        try:
            server = Server(port, udp_ttl_ms)

            for message_type, callback in message_handlers:
                server.subscribe(message_type, callback)

            for state, callback in state_handlers:
                server.on(state, callback)

            server.start()

            return server

        except OSError as e:
            msg = "Control port already in use" if e.errno == 98 else f"Server error: {str(e)}"
            raise RuntimeError(msg) from e

    def _create_video_receiver(
        self,
        port: int,
        error_callback,
        render_ratio: int
    ) -> VideoReceiver:
        video_receiver = VideoReceiver(
            port,
            error_callback,
            render_ratio=render_ratio
        )
        video_receiver.start()

        return video_receiver

    def _setup_relay_connection(self) -> Optional[tuple]:
        if not (self.relay_enable and self.relay_server and self.relay_id):
            return None

        local_bind_ports = {
            "video": self.video_port,
            "control": self.control_port
        }

        self.peer = Peer(self.relay_server, self.relay_port, self.relay_id)
        try:
            addresses = self.peer.setup("viewer", local_bind_ports)
            video_address = addresses["video"]
            logging.info(f"Relay peer setup successful, video address: {video_address}")

            return video_address

        except PeerRegistrationError as e:
            self.relay_status_message = "Peer registration failed - check server and ID!"
            logging.error(f"Peer registration failed: {e}")

            return None

    def _create_keep_alive_callback(self, video_address: tuple) -> callable:
        def keep_alive() -> None:
            if not (self.relay_enable and video_address):
                return

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

        return keep_alive

    def _setup_video_receiver(self, keep_alive_callback) -> None:
        render_ratio = self.settings.get("video", {}).get("render_ratio", 0)
        self.video_receiver = self._create_video_receiver(
            self.video_port,
            keep_alive_callback,
            render_ratio
        )
        logging.info("Video receiver started")

    def _setup_server(self) -> None:
        try:
            self.server = self._create_server(
                self.control_port,
                self.server_handlers.get("messages", []),
                self.server_handlers.get("states", []),
                self.settings.get("udp_packet_ttl", 100)
            )
            logging.info("Control server started")
        except RuntimeError as e:
            self.server_error = str(e)
            logging.error(f"Server setup failed: {str(e)}")

    def _setup_ports_task(self) -> None:
        """Background task to setup network ports and connections.

        This method orchestrates the setup of:
        1. Relay connection (if enabled)
        2. Video receiver with keep-alive callback
        3. Control server
        """
        # Setup relay connection if enabled
        video_address = self._setup_relay_connection()

        # Create keep-alive callback (works with or without relay)
        keep_alive_callback = (
            self._create_keep_alive_callback(video_address)
            if video_address
            else lambda: None
        )

        self._setup_video_receiver(keep_alive_callback)
        self._setup_server()

        logging.info("Port setup complete.")
