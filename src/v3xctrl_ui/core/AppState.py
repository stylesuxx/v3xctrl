import logging
import signal
import threading
import time
from typing import Any, Optional

import pygame

from v3xctrl_ui.core.ApplicationModel import ApplicationModel
from v3xctrl_ui.controllers.EventController import EventController
from v3xctrl_ui.controllers.SettingsController import SettingsController
from v3xctrl_ui.controllers.TimingController import TimingController
from v3xctrl_ui.menu.Menu import Menu
from v3xctrl_ui.osd.OSD import OSD
from v3xctrl_ui.core.Renderer import Renderer
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.utils.Settings import Settings
from v3xctrl_ui.controllers.input.InputController import InputController
from v3xctrl_ui.controllers.DisplayController import DisplayController
from v3xctrl_ui.network.NetworkCoordinator import NetworkCoordinator


class AppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.model = ApplicationModel(
          fullscreen=self.settings.get("video", {"fullscreen": False}).get("fullscreen", False),
          throttle=0,
          steering=0
        )

        video = settings.get("video")
        self.size = (video.get("width"), video.get("height"))

        ports = settings.get("ports", {})
        self.video_port = ports.get("video", 16384)
        self.control_port = ports.get("control", 16386)

        self.title = settings.get("settings").get("title")

        self.input_controller = InputController(settings)

        self.telemetry_context = TelemetryContext()

        self.osd = OSD(settings, self.telemetry_context)
        self.renderer = Renderer(self.size, self.settings)

        # Network coordination
        self.network_coordinator = NetworkCoordinator(self.model, self.osd)
        self.network_coordinator.on_connection_change = self._on_connection_change
        self.network_coordinator.create_network_manager(self.settings)

        # Timing
        self.timing_controller = TimingController(self.settings, self.model)

        # Display management
        self.clock = pygame.time.Clock()
        self.display_controller = DisplayController(self.model, self.size, self.title)

        # Create menu once
        self.menu = self._create_menu()

        # Event handling
        self.event_controller = EventController(
            on_quit=self._on_quit,
            on_toggle_fullscreen=self._on_toggle_fullscreen,
            menu=self.menu,
            on_menu_exit=self.update_settings,
            send_command=self.network_coordinator.send_command,
            settings=settings,
            telemetry_context=self.telemetry_context,
            gamepad_controller=self.input_controller.gamepad_controller
        )

        self._setup_signal_handling()

        self.network_coordinator.setup_ports()

        start_time = time.monotonic()
        self.model.last_control_update = start_time
        self.model.last_latency_check = start_time

        # Settings management
        self.settings_controller = SettingsController(self.settings, self.model)
        self._configure_settings_controller()

    @property
    def screen(self) -> pygame.Surface:
        return self.display_controller.get_screen()

    def update_settings(self, new_settings: Optional[Settings] = None) -> None:
        """
        Update settings after exiting menu.
        """
        self.menu.hide()

        if new_settings is None:
            new_settings = Settings()
            new_settings.save()

        self.settings_controller.update_settings(new_settings)

    def update(self) -> None:
        self.network_coordinator.process_callbacks()
        self.settings_controller.check_network_restart_complete()
        self.display_controller.update_cursor_visibility(self.menu.visible)

        now = time.monotonic()
        self.model.loop_history.append(now)

        # Handle control updates, send last values if user is in menu
        if self.timing_controller.should_update_control(now):
            try:
                throttle, steering = (0, 0)
                if not self.menu.visible:
                    throttle, steering = self.input_controller.read_inputs()

                self.model.throttle = throttle
                self.model.steering = steering

                self.network_coordinator.send_control_message(throttle, steering)
            except Exception as e:
                logging.warning(f"Input read error: {e}")
            self.timing_controller.mark_control_updated(now)

        # Handle latency checks
        if self.timing_controller.should_check_latency(now):
            self.network_coordinator.send_latency_check()
            self.timing_controller.mark_latency_checked(now)

    def tick(self) -> None:
        self.clock.tick(self.timing_controller.main_loop_fps)

    def handle_events(self) -> bool:
        """
        Handle pygame events. Returns False if application should quit.
        """
        return self.event_controller.handle_events()

    def render(self) -> None:
        # Update OSD with network data
        data_left = self.network_coordinator.get_data_queue_size()
        if self.network_coordinator.has_server_error():
            self.osd.update_debug_status("fail")

        buffer_size = self.network_coordinator.get_video_buffer_size()
        self.osd.update_buffer_queue(buffer_size)

        self.osd.update_data_queue(data_left)
        self.osd.set_control(self.model.throttle, self.model.steering)
        self.osd.set_spectator_mode(self.network_coordinator.is_spectator_mode())

        self.renderer.render_all(
            self,
            self.network_coordinator.network_manager,
            self.model.fullscreen,
            self.model.scale
        )

    def shutdown(self) -> None:
        logging.info("Shutting down...")

        # Wait for any pending network restart
        self.settings_controller.wait_for_network_restart()

        pygame.quit()

        start = time.monotonic()
        self.input_controller.shutdown()
        delta = round(time.monotonic() - start)
        logging.debug(f"Input manager shut down after {delta}s")

        self.network_coordinator.shutdown()

        delta = round(time.monotonic() - start)
        logging.info(f"Shutdown took {delta}s")

    def _on_quit(self) -> None:
        self.model.running = False

    def _on_toggle_fullscreen(self) -> None:
        self.display_controller.toggle_fullscreen()

        video_settings = self.settings.get("video", {})
        video_settings["fullscreen"] = self.model.fullscreen
        self.settings.set("video", video_settings)
        self.settings.save()

        # Update menu dimensions with new screen size
        screen_size = self.screen.get_size()
        self.menu.update_dimensions(screen_size[0], screen_size[1])

        # Refresh menu tabs to update widget states (e.g., fullscreen checkbox)
        if self.menu.visible:
            for tab in self.menu.tabs:
                tab.view.refresh_from_settings()

    def _create_menu(self) -> Menu:
        """Callback to create a new menu instance."""
        menu = Menu(
            self.screen.get_size()[0],
            self.screen.get_size()[1],
            self.input_controller.gamepad_controller,
            self.settings,
            self.network_coordinator.send_command,
            self.update_settings,
            self._signal_handler,
            self.telemetry_context
        )

        streamer_enabled = (
            self.network_coordinator.is_control_connected() and
            not self.network_coordinator.is_spectator_mode()
        )
        menu.set_tab_enabled("Streamer", streamer_enabled)

        return menu

    def _configure_settings_controller(self) -> None:
        """Configure settings controller with all necessary callbacks."""
        self.settings_controller.on_timing_update = self._on_timing_update
        self.settings_controller.on_network_update = self._on_network_update
        self.settings_controller.on_input_update = self._on_input_update
        self.settings_controller.on_osd_update = self._on_osd_update
        self.settings_controller.on_renderer_update = self._on_renderer_update
        self.settings_controller.on_display_update = self._on_display_update
        self.settings_controller.create_network_restart_thread = self._create_network_restart_thread
        self.settings_controller.network_restart_complete = self.network_coordinator.restart_complete

    def _update_network_settings(self) -> None:
        udp_ttl_ms = self.settings.get("udp_packet_ttl", 100)
        self.network_coordinator.update_ttl(udp_ttl_ms)

    def _on_timing_update(self, settings: Settings) -> None:
        self.timing_controller.settings = settings
        self.timing_controller.update_from_settings()
        self.settings = settings
        self.menu.update_settings_reference(settings)

    def _on_network_update(self, settings: Settings) -> None:
        self._update_network_settings()

    def _on_input_update(self, settings: Settings) -> None:
        self.input_controller.update_settings(settings)
        self.event_controller.update_settings(settings)

    def _on_osd_update(self, settings: Settings) -> None:
        self.osd.update_settings(settings)

    def _on_renderer_update(self, settings: Settings) -> None:
        self.renderer.settings = settings

    def _on_display_update(self, fullscreen: bool) -> None:
        self.display_controller.set_fullscreen(fullscreen)

        screen_size = self.screen.get_size()
        self.menu.update_dimensions(screen_size[0], screen_size[1])

    def _create_network_restart_thread(self, new_settings: Settings) -> threading.Thread:
        return self.network_coordinator.restart_network_manager(new_settings)

    def _on_connection_change(self, connected: bool) -> None:
        streamer_enabled = (
            connected and
            not self.network_coordinator.is_spectator_mode()
        )
        self.event_controller.set_menu_tab_enabled("Streamer", streamer_enabled)

    def _setup_signal_handling(self) -> None:
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(
        self,
        sig: Optional[int] = None,
        frame: Optional[Any] = None
    ) -> None:
        """Handle shutdown signals gracefully."""
        self.menu.hide()
        if self.model.running:
            self.model.running = False
