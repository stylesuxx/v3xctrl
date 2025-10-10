import logging
import time
from typing import Callable, Dict, Any

from pygame import Surface

from v3xctrl_control.message import Command

from v3xctrl_ui.fonts import LABEL_FONT
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

        self.video_stop_button = Button(
            "Stop Video",
            font=LABEL_FONT,
            callback=self._on_stop_video,
            width=150
        )
        self.video_start_button = Button(
            "Start Video",
            font=LABEL_FONT,
            callback=self._on_start_video,
            width=150
        )
        self.shutdown_button = Button(
            "Shutdown",
            font=LABEL_FONT,
            callback=self._on_shutdown,
            width=150
        )

        self.elements.append(self.video_stop_button)
        self.elements.append(self.video_start_button)
        self.elements.append(self.shutdown_button)

        self.headline_surfaces = {
            "actions": self._create_headline("Actions")
        }

    def draw(self, surface: Surface) -> None:
        _ = self._draw_actions_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {}

    def _on_command_callback(self, status: bool) -> None:
        # Wait a bit for the transition to not be "flickering" in case we have
        # an immediate answer
        time.sleep(1)

        self.disabled = False
        for element in self.elements:
            element.enable()

        self.on_active_toggle(False)

        logging.info(f"Received command ack: {status}")

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
        y += self._draw_headline(surface, "actions", y)

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
