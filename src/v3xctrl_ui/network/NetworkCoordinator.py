"""Network coordination for handling message routing and network lifecycle."""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt

from v3xctrl_control import State
from v3xctrl_control.message import Command, Latency, Telemetry
from v3xctrl_ui.core.dataclasses import ApplicationModel
from v3xctrl_ui.core.MainThreadDispatcher import MainThreadDispatcher
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.core.TelemetrySink import TelemetrySink
from v3xctrl_ui.network.NetworkController import NetworkController
from v3xctrl_ui.network.video.ClockOffset import ClockOffset
from v3xctrl_ui.osd.OSD import OSD

logger = logging.getLogger(__name__)


class NetworkCoordinator:
    """
    NetworkCoordinator -> NetworkController -> NetworkSetup

    Entry point for all things network:
    * Sets up network controller
    * Sends control messages, commands, latency checks
    * Setup handlers for incoming messages and state changes
    """

    def __init__(
        self,
        model: ApplicationModel,
        osd: OSD,
        telemetry_sink: TelemetrySink,
        settings: Settings,
        main_thread_dispatcher: MainThreadDispatcher,
    ):
        self.model = model
        self.osd = osd
        self.telemetry_sink = telemetry_sink
        self.main_thread_dispatcher = main_thread_dispatcher

        self.restart_complete = threading.Event()
        self._restart_thread: threading.Thread | None = None
        self.on_connection_change: Callable[[bool], None] | None = None
        self.clock_offset = ClockOffset()

        # Built last: the handlers it is given close over everything above
        self.network_controller = self.create_network_controller(settings)

    def create_network_controller(self, settings: Settings) -> NetworkController:
        handlers = self._create_handlers()
        return NetworkController(settings, handlers, self.clock_offset)

    def restart_network_controller(self, settings: Settings) -> threading.Thread:
        def _restart() -> None:
            logger.info("[NetworkController] Restarting...")
            try:
                self.network_controller.shutdown()
                self.network_controller = self.create_network_controller(settings)
                self.network_controller.setup_ports()

                logger.info("[NetworkController] Restart complete...")

            except Exception as e:
                logger.error(f"[NetworkController] Restart failed: {e}")

            finally:
                self.restart_complete.set()

        return threading.Thread(target=_restart)

    def apply_settings(self, settings: Settings) -> None:
        """Take new settings into use.

        The controller is only rebuilt while idle. Once the user has connected,
        a settings change that needs new sockets goes through restart().
        """
        if not self.model.user_connected:
            self.network_controller = self.create_network_controller(settings)

        self.update_ttl(settings.udp_packet_ttl)

    def restart(self, settings: Settings) -> None:
        self._restart_thread = self.restart_network_controller(settings)
        self._restart_thread.start()

    def is_restart_complete(self) -> bool:
        return self.restart_complete.is_set()

    def acknowledge_restart(self) -> None:
        self.restart_complete.clear()

    def wait_for_restart(self, timeout: float) -> bool:
        if self._restart_thread and self._restart_thread.is_alive():
            logger.info("Waiting for network restart to complete...")
            self._restart_thread.join(timeout=timeout)
            return not self._restart_thread.is_alive()

        return True

    def setup_ports(self):
        self.network_controller.setup_ports()

    def send_control_message(self, throttle: float, steering: float) -> None:
        # Skip sending control messages in spectator mode
        if self.network_controller.relay_spectator_mode:
            return

        self.network_controller.send_control(throttle, steering)

    def send_command(self, command: Command, callback: Callable[[bool], None]) -> None:
        # Skip sending commands in spectator mode
        if self.network_controller.relay_spectator_mode:
            logger.debug(f"Blocked command in spectator mode: {command}")
            self.main_thread_dispatcher.post(callback, False)
            return

        # Command acknowledgements arrive on a network thread
        def deferred_callback(result: bool) -> None:
            self.main_thread_dispatcher.post(callback, result)

        if not self.network_controller.send_command(command, deferred_callback):
            logger.error(f"Server is not set, cannot send command: {command}")
            callback(False)

    def send_latency_check(self) -> None:
        # Skip latency checks in spectator mode
        if self.network_controller.relay_spectator_mode:
            return

        self.network_controller.send_latency_check()

    def update_ttl(self, udp_ttl_ms: int) -> None:
        self.network_controller.update_ttl(udp_ttl_ms)

    def get_data_queue_size(self) -> int:
        return self.network_controller.get_data_queue_size()

    def get_control_buffer_size(self) -> int:
        return self.network_controller.get_control_buffer_size()

    def get_video_buffer_size(self) -> int:
        return self.network_controller.get_video_buffer_size()

    def get_video_frame(self) -> "npt.NDArray[np.uint8] | None":
        """Take the frame to display this tick.

        Call this exactly once per rendered frame: the receiver advances its
        buffer and records render timing on every call.
        """
        return self.network_controller.get_video_frame()

    def get_video_history(self) -> deque[float] | None:
        return self.network_controller.get_video_history()

    def get_control_error(self) -> str | None:
        return self.network_controller.server_error

    def is_relay_enabled(self) -> bool:
        return self.network_controller.relay_enable

    def get_relay_status_message(self) -> str:
        return self.network_controller.relay_status_message

    def has_recent_control_drops(self) -> bool:
        return self.network_controller.has_recent_control_drops()

    def has_recent_send_failures(self) -> bool:
        return self.network_controller.has_recent_send_failures()

    def has_server_error(self) -> bool:
        return bool(self.network_controller.server_error)

    def is_control_connected(self) -> bool:
        return self.model.control_connected

    def is_spectator(self) -> bool:
        return self.network_controller.relay_spectator_mode

    def shutdown(self) -> None:
        start = time.monotonic()
        self.network_controller.shutdown()
        delta = round(time.monotonic() - start)
        logger.debug(f"Network controller shut down after {delta}s")

    def _create_handlers(self) -> dict[str, Any]:
        def update_connected(state: bool) -> None:
            self.model.control_connected = state
            if self.on_connection_change:
                self.on_connection_change(state)

        def disconnect() -> None:
            self.osd.disconnect_handler()
            self.telemetry_sink.reset()

        def latency_handler(message: Latency, address: tuple[str, int]) -> None:
            self.telemetry_sink.handle_message(message)
            if message.streamer_timestamp is not None:
                self.clock_offset.update(message.timestamp, message.streamer_timestamp, time.time())

        return {
            "messages": [
                (Telemetry, lambda message, address: self.telemetry_sink.handle_message(message)),
                (Latency, latency_handler),
            ],
            "states": [
                (State.CONNECTED, lambda: self.osd.connect_handler()),
                (State.SPECTATING, lambda: self.osd.connect_handler()),
                (State.DISCONNECTED, disconnect),
                (State.CONNECTED, lambda: update_connected(True)),
                (State.SPECTATING, lambda: update_connected(True)),
                (State.DISCONNECTED, lambda: update_connected(False)),
            ],
        }
