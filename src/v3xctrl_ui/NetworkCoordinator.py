"""Network coordination for handling message routing and network lifecycle."""
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from v3xctrl_control import State
from v3xctrl_control.message import Command, Control, Latency, Telemetry

from v3xctrl_ui.NetworkManager import NetworkManager
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.ApplicationModel import ApplicationModel
from v3xctrl_ui.OSD import OSD


class NetworkCoordinator:
    def __init__(
        self,
        model: ApplicationModel,
        osd: OSD
    ):
        self.model = model
        self.osd = osd
        self.network_manager: Optional[NetworkManager] = None
        self.restart_complete = threading.Event()
        self.on_connection_change: Optional[Callable[[bool], None]] = None

    def create_network_manager(
        self,
        settings: Settings
    ) -> NetworkManager:
        handlers = self._create_handlers()
        self.network_manager = NetworkManager(settings, handlers)

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

            except Exception as e:
                logging.error(f"Network manager restart failed: {e}")

            finally:
                self.restart_complete.set()

        return threading.Thread(target=_restart)

    def send_control_message(self, throttle: float, steering: float) -> None:
        if (
            self.network_manager and
            self.network_manager.server and
            not self.network_manager.server_error
        ):
            self.network_manager.server.send(Control({
                "steering": steering,
                "throttle": throttle,
            }))

    def send_command(
        self,
        command: Command,
        callback: Callable[[bool], None]
    ) -> None:
        if self.network_manager and self.network_manager.server:
            self.network_manager.server.send_command(command, callback)
        else:
            logging.error(f"Server is not set, cannot send command: {command}")

    def send_latency_check(self) -> None:
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
                (State.DISCONNECTED, lambda: self.osd.disconnect_handler()),
                (State.CONNECTED, lambda: update_connected(True)),
                (State.DISCONNECTED, lambda: update_connected(False))
            ]
        }
