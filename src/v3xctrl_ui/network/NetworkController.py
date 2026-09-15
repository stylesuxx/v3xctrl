import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt

from v3xctrl_control import Server
from v3xctrl_control.message import Command, Control, Latency
from v3xctrl_control.UDPTransmitter import UDPTransmitter
from v3xctrl_tcp.TcpTunnel import TcpTunnel
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.network.NetworkSetup import NetworkSetup
from v3xctrl_ui.network.TcpServer import TcpServer
from v3xctrl_ui.network.video.ClockOffset import ClockOffset
from v3xctrl_ui.network.video.Receiver import Receiver
from v3xctrl_ui.network.VideoPortKeepAlive import VideoPortKeepAlive

logger = logging.getLogger(__name__)


class NetworkController:
    """Manages network connections, relay setup, and server communications."""

    def __init__(self, settings: Settings, handlers: dict[str, Any], clock_offset: ClockOffset) -> None:
        self.settings = settings
        self.server_handlers = handlers
        self.clock_offset = clock_offset

        self.video_port = settings.ports.video
        self.control_port = settings.ports.control

        # Network state
        self.video_receiver: Receiver | None = None
        self.video_keep_alive: VideoPortKeepAlive | None = None
        self.server: Server | None = None
        self.server_error: str | None = None
        self.tcp_server: TcpServer | None = None
        self.tcp_video_tunnel: TcpTunnel | None = None
        self.tcp_control_tunnel: TcpTunnel | None = None

        # Relay state
        self.relay_status_message = "Waiting for streamer..."
        self.relay_enable = False
        self.relay_server: str | None = None
        self.relay_port = 8888
        self.relay_id: str | None = None
        self.relay_spectator_mode = False
        self._setup: NetworkSetup | None = None
        self._setup_thread: threading.Thread | None = None

        self._setup_relay_if_enabled()

    def setup_relay(self, relay_server: str, relay_id: str) -> None:
        self.relay_enable = True
        self.relay_id = relay_id

        if relay_server and ":" in relay_server:
            host, port = relay_server.rsplit(":", 1)
            self.relay_server = host
            try:
                self.relay_port = int(port)
            except ValueError:
                logger.warning(
                    f"Invalid port in relay_server: '{relay_server}', falling back to default {self.relay_port}"
                )
        else:
            self.relay_server = relay_server

    def setup_ports(self) -> None:
        """Setup video and control ports in a background thread."""
        self._setup_thread = threading.Thread(target=self._setup_ports_task, daemon=True)
        self._setup_thread.start()

    def send_latency_check(self) -> None:
        if self.server and not self.server_error:
            self.server.send(Latency())

    def send_control(self, throttle: float, steering: float) -> None:
        if self.server and not self.server_error:
            self.server.send_control(Control({"steering": steering, "throttle": throttle}))

    def send_command(self, command: Command, callback: Callable[[bool], None]) -> bool:
        """Send a command. False means there was no control channel to send on."""
        if not self.server:
            return False

        self.server.send_command(command, callback)

        return True

    def has_recent_control_drops(self) -> bool:
        transmitter = self._sending_transmitter()
        if transmitter:
            return transmitter.has_recent_control_drops()

        return False

    def has_recent_send_failures(self) -> bool:
        transmitter = self._sending_transmitter()
        if transmitter:
            return transmitter.has_recent_send_failures()

        return False

    def get_video_frame(self) -> "npt.NDArray[np.uint8] | None":
        """Take the frame to display this tick.

        Call this exactly once per rendered frame: the receiver advances its
        buffer and records render timing on every call.
        """
        if self.video_receiver:
            return self.video_receiver.get_frame()

        return None

    def get_video_history(self) -> deque[float] | None:
        if self.video_receiver:
            return self.video_receiver.render_history.copy()

        return None

    def get_video_buffer_size(self) -> int:
        if self.video_receiver:
            return len(self.video_receiver.frame_buffer)

        return 0

    def get_data_queue_size(self) -> int:
        transmitter = self._sending_transmitter()
        if transmitter:
            return transmitter.queue.qsize()

        return 0

    def get_control_buffer_size(self) -> int:
        transmitter = self._sending_transmitter()
        if transmitter:
            return transmitter.get_control_buffer_size()

        return 0

    def update_ttl(self, ttl_ms: int) -> None:
        if self.server:
            self.server.update_ttl(ttl_ms)

    def shutdown(self) -> None:
        """
        Shutdown procedure needs to happen in exactly this order:

        1. Abort network setup
        2. Make sure setup thread has finished
        3. Stop control channel
        4. Stop video receiver

        NOTE: Technically stopping video and control could be swapped around.
              But video takes longer to shutdown and we would stall control
              unnecessarily.
        """

        if self._setup:
            start = time.monotonic()
            self._setup.abort()
            delta = round(time.monotonic() - start)
            logger.debug(f"Network setup aborted after {delta}s")

        if self._setup_thread and self._setup_thread.is_alive():
            start = time.monotonic()
            self._setup_thread.join()
            delta = round(time.monotonic() - start)
            logger.debug(f"Network setup thread finished after {delta}s")

        if self.server:
            start = time.monotonic()
            self.server.stop()
            self.server.join()
            delta = round(time.monotonic() - start)
            logger.debug(f"Server shut down after {delta}s")

        if self.video_keep_alive:
            self.video_keep_alive.stop()

        if self.video_receiver:
            start = time.monotonic()
            self.video_receiver.stop()
            self.video_receiver.join()
            delta = round(time.monotonic() - start)
            logger.debug(f"Video Receiver shut down after {delta}s")

        if self.tcp_server:
            self.tcp_server.stop()
            logger.debug("TCP server shut down")

        if self.tcp_video_tunnel:
            self.tcp_video_tunnel.stop()
        if self.tcp_control_tunnel:
            self.tcp_control_tunnel.stop()

    def _sending_transmitter(self) -> UDPTransmitter | None:
        """The transmitter behind a control channel that is up, if there is one.

        A `Base` only gets its transmitter once it connects, so the channel
        existing is not enough.
        """
        if self.server and not self.server_error:
            return self.server.transmitter

        return None

    def _setup_relay_if_enabled(self) -> None:
        relay = self.settings.relay
        if relay.enabled:
            self.relay_spectator_mode = relay.spectator_mode
            if relay.server and relay.id:
                self.setup_relay(relay.server, relay.id)

    def _setup_ports_task(self) -> None:
        """Background task to setup network ports and connections."""
        self._setup = NetworkSetup(self.settings)
        self._apply_setup_result(self._setup)

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
                "server": self.relay_server,
                "port": self.relay_port,
                "id": self.relay_id,
                "spectator_mode": self.relay_spectator_mode,
            }

        # Run orchestrated setup
        result = setup.orchestrate_setup(
            relay_config,
            self.server_handlers,
        )

        if result.tcp_server:
            self.tcp_server = result.tcp_server
        if result.tcp_video_tunnel:
            self.tcp_video_tunnel = result.tcp_video_tunnel
        if result.tcp_control_tunnel:
            self.tcp_control_tunnel = result.tcp_control_tunnel

        if result.relay_result and not result.relay_result.success and result.relay_result.error_message:
            self.relay_status_message = result.relay_result.error_message

        if result.video_keep_alive:
            self.video_keep_alive = result.video_keep_alive

        if result.video_receiver_result and result.video_receiver_result.video_receiver:
            self.video_receiver = result.video_receiver_result.video_receiver
            self.video_receiver.set_clock_offset(self.clock_offset)

        if result.server_result:
            if result.server_result.success:
                self.server = result.server_result.server
            else:
                self.server_error = result.server_result.error_message
