"""Network coordination for handling message routing and network lifecycle."""
import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from v3xctrl_control import State
from v3xctrl_control.message import Command, Control, Latency, Telemetry

from v3xctrl_ui.network.NetworkController import NetworkController
from v3xctrl_ui.utils.Settings import Settings
from v3xctrl_ui.core.ApplicationModel import ApplicationModel
from v3xctrl_ui.osd.OSD import OSD


class NetworkCoordinator:
    def __init__(
        self,
        model: ApplicationModel,
        osd: OSD
    ):
        self.model = model
        self.osd = osd
        self.network_manager: Optional[NetworkController] = None
        self.restart_complete = threading.Event()
        self.on_connection_change: Optional[Callable[[bool], None]] = None

        # Queue for deferring callbacks to the main thread.
        # Network callbacks (e.g. command ACKs) are invoked from background threads,
        # but UI operations like font rendering are not thread-safe. This queue
        # collects callbacks to be processed on the main thread.
        self._callback_queue: queue.Queue[Tuple[Callable, tuple]] = queue.Queue()

    def create_network_manager(
        self,
        settings: Settings
    ) -> NetworkController:
        handlers = self._create_handlers()
        self.network_manager = NetworkController(settings, handlers)

        return self.network_manager

    def setup_ports(self) -> None:
        if self.network_manager:
            self.network_manager.setup_ports()

    def restart_network_manager(
        self,
        settings: Settings
    ) -> threading.Thread:
        def _restart() -> None:
            """Background thread function to restart network manager."""
            try:
                logging.debug("Shutting down old network manager...")
                if self.network_manager:
                    self.network_manager.shutdown()

                logging.debug("Creating new network manager...")
                self.create_network_manager(settings)
                self.setup_ports()

                # Wait for server to be ready (setup_ports runs async)
                self._wait_for_server_ready()

            except Exception as e:
                logging.error(f"Network manager restart failed: {e}")

            finally:
                self.restart_complete.set()

        return threading.Thread(target=_restart)

    def _wait_for_server_ready(self, timeout: float = 10.0) -> bool:
        """Wait for the server to be ready after port setup.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if server is ready, False if timeout occurred
        """
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if (
                self.network_manager and
                (self.network_manager.server or self.network_manager.server_error)
            ):
                return True
            time.sleep(0.1)

        logging.warning("Timeout waiting for server to be ready")
        return False

    def send_control_message(self, throttle: float, steering: float) -> None:
        # Skip sending control messages in spectator mode
        if (
            self.network_manager and
            self.network_manager.relay_spectator_mode
        ):
            return

        if (
            self.network_manager and
            self.network_manager.server and
            not self.network_manager.server_error
        ):
            self.network_manager.server.send(Control({
                "steering": steering,
                "throttle": throttle,
            }))

    def process_callbacks(self) -> None:
        """Process pending callbacks on the main thread.

        This should be called from the main loop to ensure UI callbacks
        (which may do font rendering) run on the main thread.
        """
        while True:
            try:
                callback, args = self._callback_queue.get_nowait()
                callback(*args)
            except queue.Empty:
                break

    def send_command(
        self,
        command: Command,
        callback: Callable[[bool], None]
    ) -> None:
        # Skip sending commands in spectator mode
        if (
            self.network_manager and
            self.network_manager.relay_spectator_mode
        ):
            logging.debug(f"Blocked command in spectator mode: {command}")
            self._callback_queue.put((callback, (False,)))
            return

        if self.network_manager and self.network_manager.server:
            # Wrap callback to defer execution to the main thread
            def deferred_callback(result: bool) -> None:
                self._callback_queue.put((callback, (result,)))

            self.network_manager.server.send_command(command, deferred_callback)
        else:
            logging.error(f"Server is not set, cannot send command: {command}")
            callback(False)

    def send_latency_check(self) -> None:
        # Skip latency checks in spectator mode
        if (
            self.network_manager and
            self.network_manager.relay_spectator_mode
        ):
            return

        if self.network_manager:
            self.network_manager.send_latency_check()

    def update_ttl(self, udp_ttl_ms: int) -> None:
        if self.network_manager:
            self.network_manager.update_ttl(udp_ttl_ms)

    def get_data_queue_size(self) -> int:
        if self.network_manager:
            return self.network_manager.get_data_queue_size()

        return 0

    def get_video_buffer_size(self) -> int:
        if (
            self.network_manager and
            self.network_manager.video_receiver
        ):
            return len(self.network_manager.video_receiver.frame_buffer)

        return 0

    def has_server_error(self) -> bool:
        return bool(
            self.network_manager and
            self.network_manager.server_error
        )

    def is_control_connected(self) -> bool:
        return self.model.control_connected

    def is_spectator_mode(self) -> bool:
        return bool(
            self.network_manager and
            self.network_manager.relay_spectator_mode
        )

    def shutdown(self) -> None:
        if self.network_manager:
            start = time.monotonic()
            self.network_manager.shutdown()
            delta = round(time.monotonic() - start)
            logging.debug(f"Network manager shut down after {delta}s")

    def _create_handlers(self) -> Dict[str, Any]:
        def update_connected(state: bool) -> None:
            self.model.control_connected = state
            if self.on_connection_change:
                self.on_connection_change(state)

        return {
            "messages": [
                (Telemetry, lambda message, address: self.osd.message_handler(message)),
                (Latency, lambda message, address: self.osd.message_handler(message)),
            ],
            "states": [
                (State.CONNECTED, lambda: self.osd.connect_handler()),
                (State.SPECTATING, lambda: self.osd.connect_handler()),
                (State.DISCONNECTED, lambda: self.osd.disconnect_handler()),
                (State.CONNECTED, lambda: update_connected(True)),
                (State.SPECTATING, lambda: update_connected(True)),
                (State.DISCONNECTED, lambda: update_connected(False))
            ]
        }
