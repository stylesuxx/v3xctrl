# Required before importing pygame, otherwise screen might flicker during tests
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock

import pygame

from v3xctrl_ui.menu.LoadingOverlay import LoadingOverlay


class TestLoadingOverlay(unittest.TestCase):
    def setUp(self):
        self.overlay = LoadingOverlay()
        self.on_dismissed = MagicMock()

    def test_a_new_overlay_is_not_visible(self):
        self.assertFalse(self.overlay.is_visible)

    def test_show_makes_it_visible_with_the_given_text(self):
        self.overlay.show("Testing relay connection...")

        self.assertTrue(self.overlay.is_visible)
        self.assertEqual(self.overlay.text, "Testing relay connection...")

    def test_update_spins_while_waiting(self):
        self.overlay.show("Sending command...")

        self.overlay.update(0.0)
        first_angle = self.overlay.spinner_angle
        self.overlay.update(0.0)

        self.assertNotEqual(first_angle, 0)
        self.assertNotEqual(self.overlay.spinner_angle, first_angle)

    def test_update_does_nothing_while_hidden(self):
        self.overlay.update(0.0)

        self.assertFalse(self.overlay.is_visible)
        self.assertEqual(self.overlay.spinner_angle, 0)

    def test_waiting_without_a_result_stays_visible(self):
        self.overlay.show("Sending command...")

        for tick in range(10):
            self.overlay.update(float(tick))

        self.assertTrue(self.overlay.is_visible)
        self.assertEqual(self.overlay.text, "Sending command...")

    def test_a_success_result_reaches_the_screen_on_the_next_update(self):
        self.overlay.show("Sending command...")
        self.overlay.show_result(True, self.on_dismissed)

        self.assertEqual(self.overlay.text, "Sending command...")

        self.overlay.update(0.0)

        self.assertEqual(self.overlay.text, "Success!")
        self.on_dismissed.assert_not_called()

    def test_a_failed_result_reaches_the_screen_on_the_next_update(self):
        self.overlay.show("Sending command...")
        self.overlay.show_result(False, self.on_dismissed)

        self.overlay.update(0.0)

        self.assertEqual(self.overlay.text, "Failed!")

    def test_the_result_is_held_for_the_display_time(self):
        self.overlay.show("Sending command...")
        self.overlay.show_result(True, self.on_dismissed)

        self.overlay.update(100.0)
        self.overlay.update(100.0 + LoadingOverlay.RESULT_DISPLAY_SECONDS - 0.01)

        self.assertTrue(self.overlay.is_visible)
        self.on_dismissed.assert_not_called()

    def test_the_overlay_hides_and_reports_once_the_hold_expires(self):
        self.overlay.show("Sending command...")
        self.overlay.show_result(True, self.on_dismissed)

        self.overlay.update(100.0)
        self.overlay.update(100.0 + LoadingOverlay.RESULT_DISPLAY_SECONDS)

        self.assertFalse(self.overlay.is_visible)
        self.on_dismissed.assert_called_once_with(True)

    def test_the_result_is_reported_exactly_once(self):
        self.overlay.show("Sending command...")
        self.overlay.show_result(False, self.on_dismissed)

        for tick in range(10):
            self.overlay.update(100.0 + tick)

        self.on_dismissed.assert_called_once_with(False)

    def test_the_hold_is_timed_rather_than_counted_in_updates(self):
        """Updating without the clock moving must not dismiss the result."""
        self.overlay.show("Sending command...")
        self.overlay.show_result(True, self.on_dismissed)

        for _ in range(1000):
            self.overlay.update(100.0)

        self.assertTrue(self.overlay.is_visible)
        self.on_dismissed.assert_not_called()

    def test_a_result_posted_while_hidden_is_not_reported(self):
        """Nothing is being waited on, so there is no outcome to announce."""
        self.overlay.show_result(True, self.on_dismissed)

        self.overlay.update(0.0)
        self.overlay.update(100.0)

        self.assertFalse(self.overlay.is_visible)
        self.on_dismissed.assert_not_called()

    def test_showing_again_drops_the_result_of_the_previous_wait(self):
        self.overlay.show("Sending command...")
        self.overlay.show_result(True, self.on_dismissed)
        self.overlay.show("Testing relay connection...")

        for tick in range(10):
            self.overlay.update(100.0 + tick)

        self.assertTrue(self.overlay.is_visible)
        self.assertEqual(self.overlay.text, "Testing relay connection...")
        self.on_dismissed.assert_not_called()

    def test_draw_paints_within_the_surface_it_is_given(self):
        pygame.init()
        surface = pygame.Surface((800, 600), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))

        self.overlay.show("Sending command...")
        self.overlay.update(0.0)
        self.overlay.draw(surface)

        # The dimming layer covers the whole surface
        self.assertEqual(surface.get_at((0, 0)), pygame.Color(*LoadingOverlay.BACKGROUND_COLOR))
        self.assertEqual(surface.get_at((799, 599)), pygame.Color(*LoadingOverlay.BACKGROUND_COLOR))

    def test_draw_centres_on_the_surface_rather_than_a_stored_size(self):
        pygame.init()
        small = pygame.Surface((320, 240), pygame.SRCALPHA)

        self.overlay.show("Sending command...")
        self.overlay.update(0.0)
        self.overlay.draw(small)

        self.assertEqual(small.get_at((319, 239)), pygame.Color(*LoadingOverlay.BACKGROUND_COLOR))


if __name__ == "__main__":
    unittest.main()
