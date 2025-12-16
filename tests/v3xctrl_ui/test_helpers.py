import unittest
from v3xctrl_ui.helpers import calculate_widget_position


class TestCalculateWidgetPosition(unittest.TestCase):
    def setUp(self):
        self.screen_width = 1920
        self.screen_height = 1080
        self.widget_width = 100
        self.widget_height = 50

    def test_top_left_no_offset(self):
        position = calculate_widget_position(
            "top-left",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (0, 0)
        )
        self.assertEqual(position, (0, 0))

    def test_top_left_with_offset(self):
        position = calculate_widget_position(
            "top-left",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (10, 20)
        )
        self.assertEqual(position, (10, 20))

    def test_top_right_no_offset(self):
        position = calculate_widget_position(
            "top-right",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (0, 0)
        )
        # Should be at right edge (1920 - 100 = 1820)
        self.assertEqual(position, (1820, 0))

    def test_top_right_with_offset(self):
        position = calculate_widget_position(
            "top-right",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (10, 20)
        )
        # offset[0] = 10 from top, offset[1] = 20 from right
        # x = 1920 - 20 - 100 = 1800
        # y = 0 + 10 = 10
        self.assertEqual(position, (1800, 10))

    def test_bottom_left_no_offset(self):
        position = calculate_widget_position(
            "bottom-left",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (0, 0)
        )
        # Should be at bottom edge (1080 - 50 = 1030)
        self.assertEqual(position, (0, 1030))

    def test_bottom_left_with_offset(self):
        position = calculate_widget_position(
            "bottom-left",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (10, 20)
        )
        # offset[0] = 10 from bottom, offset[1] = 20 from left
        # x = 0 + 20 = 20
        # y = 1080 - 10 - 50 = 1020
        self.assertEqual(position, (20, 1020))

    def test_bottom_right_no_offset(self):
        position = calculate_widget_position(
            "bottom-right",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (0, 0)
        )
        # Should be at bottom-right corner
        # x = 1920 - 100 = 1820
        # y = 1080 - 50 = 1030
        self.assertEqual(position, (1820, 1030))

    def test_bottom_right_with_offset(self):
        position = calculate_widget_position(
            "bottom-right",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (10, 20)
        )
        # offset[0] = 10 from bottom, offset[1] = 20 from right
        # x = 1920 - 20 - 100 = 1800
        # y = 1080 - 10 - 50 = 1020
        self.assertEqual(position, (1800, 1020))

    def test_bottom_center_no_offset(self):
        position = calculate_widget_position(
            "bottom-center",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (0, 0)
        )
        # Should be centered horizontally at bottom
        # x = (1920 // 2) - (100 // 2) = 960 - 50 = 910
        # y = 1080 - 50 = 1030
        self.assertEqual(position, (910, 1030))

    def test_bottom_center_with_offset(self):
        position = calculate_widget_position(
            "bottom-center",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (10, 20)
        )
        # offset[0] = 10 from bottom, offset[1] = 20 horizontal adjustment
        # x = (1920 // 2) - 20 - (100 // 2) = 960 - 20 - 50 = 890
        # y = 1080 - 10 - 50 = 1020
        self.assertEqual(position, (890, 1020))

    def test_unknown_alignment_returns_origin(self):
        position = calculate_widget_position(
            "unknown-alignment",
            self.widget_width,
            self.widget_height,
            self.screen_width,
            self.screen_height,
            (10, 20)
        )
        self.assertEqual(position, (0, 0))

    def test_different_screen_size(self):
        position = calculate_widget_position(
            "bottom-right",
            50,
            25,
            800,
            600,
            (5, 10)
        )
        # x = 800 - 10 - 50 = 740
        # y = 600 - 5 - 25 = 570
        self.assertEqual(position, (740, 570))

    def test_zero_widget_size(self):
        position = calculate_widget_position(
            "top-right",
            0,
            0,
            1920,
            1080,
            (0, 0)
        )
        self.assertEqual(position, (1920, 0))


if __name__ == "__main__":
    unittest.main()
