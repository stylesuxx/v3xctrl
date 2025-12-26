import logging
from typing import Callable, Dict, Any

from pygame import Surface

from v3xctrl_control.message import Command

from v3xctrl_ui.utils.fonts import LABEL_FONT
from v3xctrl_ui.utils.i18n import t
from v3xctrl_ui.menu.input import Button
from v3xctrl_ui.utils.Settings import Settings
from v3xctrl_ui.core.TelemetryContext import TelemetryContext

from .Tab import Tab
from .VerticalLayout import VerticalLayout


class StreamerTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int,
        on_active_toggle: Callable[[bool], None],
        send_command: Callable[[Command, Callable[[bool], None]], None],
        telemetry_context: TelemetryContext
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.on_active_toggle = on_active_toggle
        self.send_command = send_command
        self.telemetry_context = telemetry_context

        self.button_width = 200

        self.video_stop_button = Button(
            t("Stop Video"),
            font=LABEL_FONT,
            callback=self._on_stop_video,
            width=self.button_width
        )
        self.video_start_button = Button(
            t("Start Video"),
            font=LABEL_FONT,
            callback=self._on_start_video,
            width=self.button_width
        )

        self.recording_stop_button = Button(
            t("Stop Recording"),
            font=LABEL_FONT,
            callback=self._on_stop_recording,
            width=self.button_width
        )
        self.recording_start_button = Button(
            t("Start Recording"),
            font=LABEL_FONT,
            callback=self._on_start_recording,
            width=self.button_width
        )

        self.shutdown_button = Button(
            t("Shutdown"),
            font=LABEL_FONT,
            callback=self._on_shutdown,
            width=self.button_width
        )
        self.restart_button = Button(
            t("Restart"),
            font=LABEL_FONT,
            callback=self._on_restart,
            width=self.button_width

        )

        self.shell_stop_button = Button(
            "Stop Reverse Shell",
            font=LABEL_FONT,
            callback=self._on_stop_shell,
            width=self.button_width
        )
        self.shell_start_button = Button(
            "Start Reverse Shell",
            font=LABEL_FONT,
            callback=self._on_start_shell,
            width=self.button_width
        )

        self.elements_col_1 = [
            self.video_start_button,
            self.recording_start_button,
            self.shell_start_button,
            self.shutdown_button,
        ]

        self.elements_col_2 = [
            self.video_stop_button,
            self.recording_stop_button,
            self.shell_stop_button,
            self.restart_button,
        ]

        self.headline_surfaces = {
            "actions": self._create_headline(t("Actions"))
        }

        self.col_1_layout = VerticalLayout()
        for element in self.elements_col_1:
            self.col_1_layout.add(element)

        self.col_2_layout = VerticalLayout(self.padding * 2 + self.button_width)
        for element in self.elements_col_2:
            self.col_2_layout.add(element)

        self.elements = self.elements_col_1 + self.elements_col_2

    def draw(self, surface: Surface) -> None:
        services = self.telemetry_context.get_services()
        gst = self.telemetry_context.get_gst()

        if services.reverse_shell:
            self.shell_start_button.disable()
            self.shell_stop_button.enable()
        else:
            self.shell_start_button.enable()
            self.shell_stop_button.disable()

        if services.video:
            self.video_start_button.disable()
            self.video_stop_button.enable()

            if gst.recording:
                self.recording_start_button.disable()
                self.recording_stop_button.enable()
            else:
                self.recording_start_button.enable()
                self.recording_stop_button.disable()
        else:
            self.video_start_button.enable()
            self.video_stop_button.disable()

            # Disable recording buttons if video service is not running anyway
            self.recording_start_button.disable()
            self.recording_stop_button.disable()

        _ = self._draw_actions_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {}

    def _on_command_callback(self, status: bool) -> None:
        self.on_active_toggle(False)
        logging.info(f"Received command ack: {status}")

    def _on_action(self, command: Command) -> None:
        self.on_active_toggle(True)
        self.send_command(command, self._on_command_callback)

    def _on_service_action(self, name: str, action: str) -> None:
        command = Command(
            "service", {
                "name": name,
                "action": action,
            }
        )
        self._on_action(command)

    def _on_stop_video(self) -> None:
        self._on_service_action("v3xctrl-video", "stop")

    def _on_start_video(self) -> None:
        self._on_service_action("v3xctrl-video", "start")

    def _on_stop_shell(self) -> None:
        self._on_service_action("v3xctrl-reverse-shell", "stop")

    def _on_start_shell(self) -> None:
        self._on_service_action("v3xctrl-reverse-shell", "start")

    def _on_recording_action(self, action: str) -> None:
        command = Command("recording", {"action": action})
        self._on_action(command)

    def _on_stop_recording(self) -> None:
        self._on_recording_action("stop")

    def _on_start_recording(self) -> None:
        self._on_recording_action("start")

    def _on_shutdown(self) -> None:
        self.on_active_toggle(True)
        command = Command("shutdown")
        self.send_command(command, self._on_command_callback)

    def _on_restart(self) -> None:
        self.on_active_toggle(True)
        command = Command("restart")
        self.send_command(command, self._on_command_callback)

    def _draw_actions_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "actions", y)

        _ = self.col_1_layout.draw(surface, y)
        return self.col_2_layout.draw(surface, y)
