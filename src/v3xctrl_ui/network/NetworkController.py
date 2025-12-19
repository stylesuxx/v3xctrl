import logging
import threading
import time
from typing import Any, Dict, Optional

from v3xctrl_control import Server
from v3xctrl_control.message import Latency
from v3xctrl_udp_relay.Peer import Peer

from v3xctrl_ui.utils.helpers import get_external_ip
from v3xctrl_ui.utils.Settings import Settings
from v3xctrl_ui.network.VideoReceiverPyAV import VideoReceiverPyAV as VideoReceiver  # noqa: F401
from v3xctrl_ui.network.NetworkSetup import NetworkSetup


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

    def _apply_setup_result(self, setup: NetworkSetup) -> None:
        """
        Apply setup result by running orchestration and updating state.

        Args:
            setup: NetworkSetup instance to run orchestration
        """
        # Prepare relay config if enabled
        relay_config = None
        if self.relay_enable and self.relay_server and self.relay_id:
            relay_config = {
                'server': self.relay_server,
                'port': self.relay_port,
                'id': self.relay_id
            }

        # Run orchestrated setup
        result = setup.orchestrate_setup(relay_config, self.server_handlers)

        # Apply results to controller state
        if result.relay_result:
            if not result.relay_result.success:
                self.relay_status_message = result.relay_result.error_message
            else:
                self.peer = result.relay_result.peer

        if result.video_receiver_result and result.video_receiver_result.success:
            self.video_receiver = result.video_receiver_result.video_receiver

        if result.server_result:
            if result.server_result.success:
                self.server = result.server_result.server
            else:
                self.server_error = result.server_result.error_message

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

    def _setup_ports_task(self) -> None:
        """Background task to setup network ports and connections."""
        setup = NetworkSetup(self.settings)
        self._apply_setup_result(setup)
