# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest

import pygame

from v3xctrl_ui.osd.widgets.SignalQualityWidget import SignalQualityWidget, SignalQuality


class TestSignalQualityWidget(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.widget = SignalQualityWidget(position=(5, 10), size=(100, 50))
        self.screen = pygame.Surface((200, 100))

    def test_rsrp_to_dbm_mapping(self):
        self.assertEqual(self.widget._rsrp_to_dbm(255), -140)
        self.assertEqual(self.widget._rsrp_to_dbm(140), 0)
        self.assertEqual(self.widget._rsrp_to_dbm(130), -10)

    def test_rsrq_to_dbm_mapping(self):
        self.assertIsNone(self.widget._rsrq_to_dbm(255))
        self.assertAlmostEqual(self.widget._rsrq_to_dbm(39), -0.5, places=1)
        self.assertAlmostEqual(self.widget._rsrq_to_dbm(10), -15.0, places=1)

    def test_get_bars(self):
        self.assertEqual(self.widget._get_bars(60), 5)
        self.assertEqual(self.widget._get_bars(59), 4)
        self.assertEqual(self.widget._get_bars(50), 4)
        self.assertEqual(self.widget._get_bars(49), 3)
        self.assertEqual(self.widget._get_bars(46), 3)
        self.assertEqual(self.widget._get_bars(35), 2)
        self.assertEqual(self.widget._get_bars(30), 2)
        self.assertEqual(self.widget._get_bars(29), 1)
        self.assertEqual(self.widget._get_bars(20), 1)
        self.assertEqual(self.widget._get_bars(19), 0)
        self.assertEqual(self.widget._get_bars(0), 0)

    def test_get_quality_boundaries(self):
        self.assertEqual(self.widget._get_quality(34), SignalQuality.EXCELLENT)
        self.assertEqual(self.widget._get_quality(21), SignalQuality.GOOD)
        self.assertEqual(self.widget._get_quality(20), SignalQuality.GOOD)
        self.assertEqual(self.widget._get_quality(12), SignalQuality.GOOD)
        self.assertEqual(self.widget._get_quality(11), SignalQuality.FAIR)
        self.assertEqual(self.widget._get_quality(2), SignalQuality.FAIR)
        self.assertEqual(self.widget._get_quality(1), SignalQuality.POOR)
        self.assertEqual(self.widget._get_quality(0), SignalQuality.POOR)

    def test_draw_runs_without_error(self):
        signals = [
            {'rsrp': 220, 'rsrq': 59},
            {'rsrp': 190, 'rsrq': 10},
            {'rsrp': 255, 'rsrq': 255},
        ]
        for sig in signals:
            self.widget.draw(self.screen, sig)

    def test_draw_no_modem_state(self):
        self.widget.draw(self.screen, {'rsrp': -1, 'rsrq': -1})

    def test_invalid_rsrq_still_maps(self):
        self.assertEqual(self.widget._get_quality(255), SignalQuality.POOR)
        self.assertEqual(self.widget._get_quality(-1), SignalQuality.POOR)

    def test_invalid_rsrp_still_draws(self):
        signals = [{'rsrp': -1, 'rsrq': 15}, {'rsrp': 999, 'rsrq': 15}]
        for sig in signals:
            self.widget.draw(self.screen, sig)


if __name__ == "__main__":
    unittest.main()
