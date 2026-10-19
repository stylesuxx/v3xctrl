import unittest

from v3xctrl_e2e.preflight import check_load, check_viewer_flags, has_viewer_titles


class TestViewerFlags(unittest.TestCase):
    def test_current_viewer_passes(self):
        self.assertEqual(check_viewer_flags("usage: v3xctrl [--log LOG] [--config CONFIG] [--connect]"), [])

    def test_old_build_is_named(self):
        failures = check_viewer_flags("usage: v3xctrl [-h] [--log LOG] [--config CONFIG]")

        self.assertEqual(len(failures), 1)
        self.assertIn("--connect", failures[0])


class TestViewerTitles(unittest.TestCase):
    def test_title_support_is_read_from_the_usage_text(self):
        self.assertTrue(has_viewer_titles("usage: v3xctrl [--connect] [--title TITLE]"))
        self.assertFalse(has_viewer_titles("usage: v3xctrl [--connect]"))


class TestLoad(unittest.TestCase):
    def test_idle_streamer_passes(self):
        self.assertEqual(check_load({"load_average": [0.5, 0.4, 0.3], "cpu_count": 4}, maximum_load_per_cpu=0.75), [])

    def test_busy_streamer_is_refused(self):
        failures = check_load({"load_average": [3.9, 3.0, 2.0], "cpu_count": 4}, maximum_load_per_cpu=0.75)

        self.assertEqual(len(failures), 1)
