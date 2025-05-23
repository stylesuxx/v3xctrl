import unittest
import pygame
from pygame import Surface
from v3xctrl_ui.widgets.SignalQualityWidget import SignalQualityWidget, SignalQuality


class TestSignalQualityWidget(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.widget = SignalQualityWidget(position=(5, 10), size=(100, 50))
        self.screen = pygame.Surface((200, 100))

    def tearDown(self):
        pygame.quit()

    def test_initial_geometry(self):
        w = self.widget
        # Basic geometry checks
        self.assertEqual(w.BAR_COUNT, 5)
        self.assertTrue(w.bar_spacing > 0)
        self.assertTrue(w.bar_width > 0)
        self.assertTrue(w.bar_max_height > 0)
        self.assertTrue(w.extra_right_padding in (0,1))

    def test_rsrp_to_dbm_mapping(self):
        w = self.widget
        self.assertEqual(w._rsrp_to_dbm(255), -140)
        self.assertEqual(w._rsrp_to_dbm(140), 0)
        self.assertEqual(w._rsrp_to_dbm(130), -10)

    def test_rsrq_to_dbm_mapping(self):
        w = self.widget
        self.assertEqual(w._rsrq_to_dbm(255), None)
        self.assertAlmostEqual(w._rsrq_to_dbm(39), -0.5, places=1)
        self.assertAlmostEqual(w._rsrq_to_dbm(10), -15.0, places=1)

    def test_get_bars(self):
        w = self.widget
        self.assertEqual(w._get_bars(60), 5)
        self.assertEqual(w._get_bars(55), 4)
        self.assertEqual(w._get_bars(45), 3)
        self.assertEqual(w._get_bars(35), 2)
        self.assertEqual(w._get_bars(25), 1)

    def test_get_quality_boundaries(self):
        w = self.widget
        self.assertEqual(w._get_quality(26), SignalQuality.EXCELLENT)
        self.assertEqual(w._get_quality(20), SignalQuality.GOOD)
        self.assertEqual(w._get_quality(9), SignalQuality.FAIR)
        self.assertEqual(w._get_quality(5), SignalQuality.POOR)

    def test_draw_runs_without_error(self):
        w = self.widget

        signals = [
            {'rsrp': 220, 'rsrq': 59},  # Excellent
            {'rsrp': 190, 'rsrq': 10},  # Poor
            {'rsrp': 255, 'rsrq': 255}, # special edge
        ]
        for sig in signals:
            try:
                w.draw(self.screen, sig)
            except Exception as e:
                self.fail(f"Draw failed for signal {sig}: {e}")


if __name__ == "__main__":
    unittest.main()
