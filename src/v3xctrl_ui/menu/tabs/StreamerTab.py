import logging
from pygame import Surface
import time

from v3xctrl_control.Message import Command

from v3xctrl_ui.fonts import LABEL_FONT
from v3xctrl_ui.menu.input import Button
from v3xctrl_ui.menu.tabs.Tab import Tab


class StreamerTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int, on_active_toggle: callable, send_command: callable):
        super().__init__(settings, width, height, padding, y_offset)

        self.on_active_toggle = on_active_toggle
        self.send_command = send_command

        self.disabled = False
        self.elements = []

        self.video_stop_button = Button(
            "Stop Video",
            150, 40,
            font=LABEL_FONT,
            callback=self._on_stop_video
        )
        self.video_start_button = Button(
            "Start Video",
            150, 40,
            font=LABEL_FONT,
            callback=self._on_start_video
        )
        self.shutdown_button = Button(
            "Shutdown",
            150, 40,
            font=LABEL_FONT,
            callback=self._on_shutdown
        )

        self.elements.append(self.video_stop_button)
        self.elements.append(self.video_start_button)
        self.elements.append(self.shutdown_button)

    def _on_command_callback(self, status: bool):
        # Wait a bit for the transition to not be "flickering"
        time.sleep(1)

        self.disabled = False
        for element in self.elements:
            element.enable()

        self.on_active_toggle(False)

        logging.debug(f"Received command status: {status}")

    def _on_video_action(self, action: str) -> None:
        self.disabled = True
        self.on_active_toggle(True)
        for element in self.elements:
            element.disable()

        command = Command(
            "service", {
                "action": action,
                "name": "v3xctrl-video",
            }
        )
        self.send_command(command, self._on_command_callback)

    def _on_stop_video(self) -> None:
        self._on_video_action("stop")

    def _on_start_video(self) -> None:
        self._on_video_action("start")

    def _on_shutdown(self) -> None:
        self.disabled = True
        self.on_active_toggle(True)
        for element in self.elements:
            element.disable()

        command = Command("shutdown")
        self.send_command(command, self._on_command_callback)

    def _draw_actions_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        self._draw_headline(surface, "Actions", y)
        y += self.y_offset_headline

        self.video_start_button.set_position(self.padding, y)
        self.video_start_button.draw(surface)

        self.video_stop_button.set_position(
            self.padding * 2 + self.video_start_button.get_size()[0],
            y
        )
        self.video_stop_button.draw(surface)
        y += self.video_stop_button.get_size()[1]

        y += self.padding
        self.shutdown_button.set_position(self.padding, y)
        self.shutdown_button.draw(surface)
        y += self.video_stop_button.get_size()[1]

        return y

    def draw(self, surface: Surface):
        _ = self._draw_actions_section(surface, 0)

    def get_settings(self) -> dict:
        return {}
