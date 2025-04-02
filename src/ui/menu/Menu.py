import pygame
from pygame import Surface
import pygame.freetype
from typing import Callable

from ui.Settings import Settings
from ui.menu.NumberInput import NumberInput
from ui.menu.Checkbox import Checkbox
from ui.menu.Button import Button
from ui.menu.KeyMappingWidget import KeyMappingWidget


class Menu:
    BG_COLOR = (30, 30, 30)
    TAB_ACTIVE_COLOR = (90, 90, 90)
    TAB_INACTIVE_COLOR = (50, 50, 50)
    TAB_SEPARATOR_COLOR = BG_COLOR
    FONT_COLOR = (255, 255, 255)
    LINE_COLOR = (255, 255, 255)

    def __init__(self,
                 width: int,
                 height: int,
                 settings: Settings,
                 callback: Callable[[], None]):
        self.width = width
        self.height = height
        self.settings = settings
        self.callback = callback

        self.font = pygame.freetype.SysFont("freesansbold", 30)
        self.font_headline = pygame.freetype.SysFont("freesansbold", 30)
        self.text_font = pygame.freetype.SysFont("freesans", 16)

        self.button_font = pygame.freetype.SysFont("freesansbold", 30)
        self.label_font = pygame.freetype.SysFont("freesansbold", 20)
        self.mono_font = pygame.freetype.SysFont("couriernew", 20)

        self.tabs = ["General", "Video", "Input"]
        self.active_tab = self.tabs[0]

        self.tab_height = 60
        self.footer_height = 60
        self.padding = 20

        self.tab_rects = self._generate_tab_rects()

        button_y = self.height - self.footer_height
        self.save_button = Button(
            "Save",
            100, 40,
            self.button_font,
            self._save_button_callback)
        self.save_button.set_position(self.width - 240, button_y)

        self.exit_button = Button(
            "Back",
            100, 40,
            self.button_font,
            self._exit_button_callback)
        self.exit_button.set_position(self.width - 120, button_y)

        # General widgets
        self.debug = self.settings.get("debug", False)
        self.ports = self.settings.get("ports", {})

        self.video_input = NumberInput(
            "Video",
            self.padding,
            self.tab_height + self.padding + 60,
            90, 75,
            1, 65535,
            self.label_font, self.mono_font,
            on_change=lambda v: self._on_port_change("video", v)
        )
        self.control_input = NumberInput(
            "Control",
            self.padding,
            self.tab_height + self.padding + 100,
            90, 75,
            1, 65535,
            self.label_font, self.mono_font,
            on_change=lambda v: self._on_port_change("control", v)
        )

        # Miscellaneous widgets
        self.debug_checkbox = Checkbox(
            label="Enable Debug Overlay",
            font=self.label_font,
            checked=self.settings.get("debug", False),
            on_change=lambda v: self._on_debug_change(v)
        )

        # Input widgets
        keyboard_controls = self.settings.get("controls", {}).get("keyboard", {})
        self.key_widgets = []

        for name, key in keyboard_controls.items():
            widget = KeyMappingWidget(
                control_name=name,
                key_code=key,
                font=self.label_font,
                on_key_change=lambda new_key, name=name: self._on_control_key_change(name, new_key),
                on_remap_toggle=self._on_remap_toggle
            )
            self.key_widgets.append(widget)

        self.video_input.value = str(self.ports["video"])
        self.video_input.cursor_pos = len(self.video_input.value)

        self.control_input.value = str(self.ports["control"])
        self.control_input.cursor_pos = len(self.control_input.value)

        self.background = pygame.Surface((self.width, self.height))
        self.background.fill(self.BG_COLOR)

    def _on_remap_toggle(self, is_remapping: bool):
        if is_remapping:
            self.save_button.disable()
            self.exit_button.disable()
            for widget in self.key_widgets:
                widget.disable()
        else:
            self.save_button.enable()
            self.exit_button.enable()
            for widget in self.key_widgets:
                widget.enable()

    def _on_port_change(self, name, value):
        self.ports[name] = int(value)

    def _on_debug_change(self, value):
        self.debug = value

    def _save_button_callback(self):
        if self.active_tab == "General":
            self.settings.set("ports", self.ports)
            self.settings.set("debug", self.debug)

        elif self.active_tab == "Input":
            pass

        self.settings.save()

    def _exit_button_callback(self):
        self.active_tab = self.tabs[0]
        self.callback()

    def _on_control_key_change(self, control_name, key_code):
        controls = self.settings.get("controls")
        keyboard = controls.setdefault("keyboard", {})
        keyboard[control_name] = key_code

    def _generate_tab_rects(self):
        tab_width = self.width // len(self.tabs)
        return {
            name: pygame.Rect(i * tab_width, 0, tab_width, self.tab_height)
            for i, name in enumerate(self.tabs)
        }

    def handle_event(self, event):
        self.save_button.handle_event(event)
        self.exit_button.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for tab, rect in self.tab_rects.items():
                if rect.collidepoint(event.pos):
                    self.active_tab = tab

        if self.active_tab == "General":
            self.video_input.handle_event(event)
            self.control_input.handle_event(event)
            self.debug_checkbox.handle_event(event)

        elif self.active_tab == "Input":
            for widget in self.key_widgets:
                widget.handle_event(event)

    def _draw_headline(self, surface: Surface, title: str, y: int) -> int:
        heading_surface, _ = self.font_headline.render(title, self.FONT_COLOR)
        heading_pos = (self.padding, y)
        surface.blit(heading_surface, heading_pos)
        pygame.draw.line(surface, self.LINE_COLOR,
                         (self.padding, y + 40),
                         (self.width - self.padding, y + 40), 2)

        return y + 40

    def draw(self, surface: Surface):
        surface.blit(self.background, (0, 0))

        for i, (tab, rect) in enumerate(self.tab_rects.items()):
            color = self.TAB_ACTIVE_COLOR if tab == self.active_tab else self.TAB_INACTIVE_COLOR
            pygame.draw.rect(surface, color, rect)
            if i > 0:
                pygame.draw.line(surface, self.TAB_SEPARATOR_COLOR, rect.topleft, rect.bottomleft, 2)
            label_surface, label_rect = self.font.render(tab, self.FONT_COLOR)
            label_rect.center = rect.center
            surface.blit(label_surface, label_rect)

        self.save_button.draw(surface)
        self.exit_button.draw(surface)

        if self.active_tab == "Input":
            ports_section_y = self.tab_height + self.padding
            baseline = self._draw_headline(surface, "Keyboard", ports_section_y)

            # Draw each key remapping row
            row_y = baseline + 20
            for widget in self.key_widgets:
                widget.set_position(self.padding, row_y)

                widget.draw(surface)
                row_y += 40

        if self.active_tab == "General":
            ports_section_y = self.tab_height + self.padding
            self._draw_headline(surface, "Ports", ports_section_y)

            self.video_input.draw(surface)
            self.control_input.draw(surface)

            # Note about restarting
            note_text = "Remember to restart the app after changing the ports!"
            note_surface, note_rect = self.text_font.render(note_text, self.FONT_COLOR)
            note_rect.topleft = (
                self.padding,
                self.control_input.y + self.control_input.input_height + 20
            )

            # --- Miscellaneous section ---
            misc_section_y = note_rect.bottom + self.padding + 10
            baseline = self._draw_headline(surface, "Miscellaneous", misc_section_y)

            # Set checkbox y dynamically
            y = baseline + 20
            self.debug_checkbox.set_position(self.padding, y)
            self.debug_checkbox.draw(surface)

            surface.blit(note_surface, note_rect)
