import logging
from typing import Callable, Dict, Any

from pygame import Surface

from v3xctrl_control.message import Command

from v3xctrl_ui.fonts import LABEL_FONT
from v3xctrl_ui.i18n import t
from v3xctrl_ui.menu.input import Button
from v3xctrl_ui.menu.tabs.Tab import Tab
from v3xctrl_ui.Settings import Settings


class StreamerTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int,
        on_active_toggle: Callable[[bool], None],
        send_command: Callable[[Command, Callable[[bool], None]], None]
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.on_active_toggle = on_active_toggle
        self.send_command = send_command

        self.disabled = False
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

        self.elements.append(self.video_stop_button)
        self.elements.append(self.video_start_button)

        self.elements.append(self.recording_stop_button)
        self.elements.append(self.recording_start_button)

        self.elements.append(self.shutdown_button)
        self.elements.append(self.restart_button)
        self.elements.append(self.shell_stop_button)
        self.elements.append(self.shell_start_button)

        self.headline_surfaces = {
            "actions": self._create_headline(t("Actions"))
        }

    def draw(self, surface: Surface) -> None:
        _ = self._draw_actions_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {}

    def _on_command_callback(self, status: bool) -> None:
        self.disabled = False
        for element in self.elements:
            element.enable()

        self.on_active_toggle(False)

        logging.info(f"Received command ack: {status}")

    def _on_action(self, command: Command) -> None:
        self.disabled = True
        self.on_active_toggle(True)
        for element in self.elements:
            element.disable()

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
        self.disabled = True
        self.on_active_toggle(True)
        for element in self.elements:
            element.disable()

        command = Command("shutdown")
        self.send_command(command, self._on_command_callback)

    def _on_restart(self) -> None:
        self.disabled = True
        self.on_active_toggle(True)
        for element in self.elements:
            element.disable()

        command = Command("restart")
        self.send_command(command, self._on_command_callback)

    def _draw_actions_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "actions", y)

        self.video_start_button.set_position(self.padding, y)
        self.video_start_button.draw(surface)

        self.video_stop_button.set_position(
            self.padding * 2 + self.video_start_button.width,
            y
        )
        self.video_stop_button.draw(surface)
        y += self.video_stop_button.get_size()[1]

        y += self.padding
        self.recording_start_button.set_position(self.padding, y)
        self.recording_start_button.draw(surface)

        self.recording_stop_button.set_position(
            self.padding * 2 + self.recording_start_button.width,
            y
        )
        self.recording_stop_button.draw(surface)
        y += self.video_stop_button.get_size()[1]

        y += self.padding
        self.shell_start_button.set_position(self.padding, y)
        self.shell_start_button.draw(surface)

        self.shell_stop_button.set_position(
            self.padding * 2 + self.shell_stop_button.width,
            y
        )
        self.shell_stop_button.draw(surface)
        y += self.shell_stop_button.get_size()[1]

        y += self.padding
        self.shutdown_button.set_position(self.padding, y)
        self.shutdown_button.draw(surface)

        self.restart_button.set_position(
            self.padding * 2 + self.shutdown_button.width,
            y
        )
        self.restart_button.draw(surface)
        y += self.video_stop_button.get_size()[1]

        return y
