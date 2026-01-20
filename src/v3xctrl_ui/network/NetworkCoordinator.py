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
    """
    NetworkCoordinator -> NetworkController -> NetworkSetup

    Entry point for all things network:
    * Sets up network controller
    * Sends control messages, commands, latency checks
    * Setup handlers for incoming messages and state changes
    * Handles callbacks that should deferred to the main thread
    """
    def __init__(
        self,
        model: ApplicationModel,
        osd: OSD
    ):
        self.model = model
        self.osd = osd

        self.network_controller: Optional[NetworkController] = None
        self.restart_complete = threading.Event()
        self.on_connection_change: Optional[Callable[[bool], None]] = None

        # Queue for deferring callbacks to the main thread.
        # Network callbacks (e.g. command ACKs) are invoked from background threads,
        # but UI operations like font rendering are not thread-safe. This queue
        # collects callbacks to be processed on the main thread.
        self._callback_queue: queue.Queue[Tuple[Callable, tuple]] = queue.Queue()

    def create_network_controller(
        self,
        settings: Settings
    ) -> NetworkController:
        handlers = self._create_handlers()
        return NetworkController(settings, handlers)

    def restart_network_controller(
        self,
        settings: Settings
    ) -> threading.Thread:
        def _restart() -> None:
            logging.info("[NetworkController] Restarting...")
            try:
                if self.network_controller:
                    self.network_controller.shutdown()

                self.network_controller = self.create_network_controller(settings)
                self.network_controller.setup_ports()

                logging.info("[NetworkController] Restart complete...")

            except Exception as e:
                logging.error(f"[NetworkController] Restart failed: {e}")

            finally:
                self.restart_complete.set()

        return threading.Thread(target=_restart)

    def setup_ports(self):
        if self.network_controller:
            self.network_controller.setup_ports()

    def send_control_message(self, throttle: float, steering: float) -> None:
        # Skip sending control messages in spectator mode
        if (
            self.network_controller and
            self.network_controller.relay_spectator_mode
        ):
            return

        if (
            self.network_controller and
            self.network_controller.server and
            not self.network_controller.server_error
        ):
            self.network_controller.server.send(Control({
                "steering": steering,
                "throttle": throttle,
            }))

    def send_command(
        self,
        command: Command,
        callback: Callable[[bool], None]
    ) -> None:
        # Skip sending commands in spectator mode
        if (
            self.network_controller and
            self.network_controller.relay_spectator_mode
        ):
            logging.debug(f"Blocked command in spectator mode: {command}")
            self._callback_queue.put((callback, (False,)))
            return

        if self.network_controller and self.network_controller.server:
            # Wrap callback to defer execution to the main thread
            def deferred_callback(result: bool) -> None:
                self._callback_queue.put((callback, (result,)))

            self.network_controller.server.send_command(command, deferred_callback)
        else:
            logging.error(f"Server is not set, cannot send command: {command}")
            callback(False)

    def send_latency_check(self) -> None:
        # Skip latency checks in spectator mode
        if (
            self.network_controller and
            self.network_controller.relay_spectator_mode
        ):
            return

        if self.network_controller:
            self.network_controller.send_latency_check()

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

    def update_ttl(self, udp_ttl_ms: int) -> None:
        if self.network_controller:
            self.network_controller.update_ttl(udp_ttl_ms)

    def get_data_queue_size(self) -> int:
        if self.network_controller:
            return self.network_controller.get_data_queue_size()

        return 0

    def get_video_buffer_size(self) -> int:
        if (
            self.network_controller and
            self.network_controller.video_receiver
        ):
            return len(self.network_controller.video_receiver.frame_buffer)

        return 0

    def has_server_error(self) -> bool:
        return bool(
            self.network_controller and
            self.network_controller.server_error
        )

    def is_control_connected(self) -> bool:
        return self.model.control_connected

    def is_spectator(self) -> bool:
        return bool(
            self.network_controller and
            self.network_controller.relay_spectator_mode
        )

    def shutdown(self) -> None:
        if self.network_controller:
            start = time.monotonic()
            self.network_controller.shutdown()
            delta = round(time.monotonic() - start)
            logging.debug(f"Network controller shut down after {delta}s")

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
