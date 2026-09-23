import math
import unittest

from v3xctrl_helper.helper import EARTH_RADIUS_METERS, color_to_hex, haversine_meters, is_int


class TestColorToHex(unittest.TestCase):
    def test_black(self):
        self.assertEqual(color_to_hex((0, 0, 0)), "#000000")

    def test_white(self):
        self.assertEqual(color_to_hex((255, 255, 255)), "#FFFFFF")

    def test_red(self):
        self.assertEqual(color_to_hex((255, 0, 0)), "#FF0000")

    def test_green(self):
        self.assertEqual(color_to_hex((0, 255, 0)), "#00FF00")

    def test_blue(self):
        self.assertEqual(color_to_hex((0, 0, 255)), "#0000FF")

    def test_arbitrary_color(self):
        self.assertEqual(color_to_hex((171, 205, 239)), "#ABCDEF")

    def test_single_digit_hex_values_are_zero_padded(self):
        self.assertEqual(color_to_hex((1, 2, 3)), "#010203")


class TestIsInt(unittest.TestCase):
    def test_positive_integer(self):
        self.assertTrue(is_int("42"))

    def test_negative_integer(self):
        self.assertTrue(is_int("-7"))

    def test_zero(self):
        self.assertTrue(is_int("0"))

    def test_float_string(self):
        self.assertFalse(is_int("3.14"))

    def test_empty_string(self):
        self.assertFalse(is_int(""))

    def test_alphabetic_string(self):
        self.assertFalse(is_int("abc"))

    def test_mixed_string(self):
        self.assertFalse(is_int("12abc"))

    def test_whitespace_only(self):
        self.assertFalse(is_int("   "))

    def test_large_integer(self):
        self.assertTrue(is_int("999999999999"))


if __name__ == "__main__":
    unittest.main()


class TestHaversineMeters(unittest.TestCase):
    def test_same_point_is_zero(self):
        self.assertEqual(haversine_meters(52.52, 13.405, 52.52, 13.405), 0.0)

    def test_one_degree_of_latitude(self):
        expected = EARTH_RADIUS_METERS * math.pi / 180
        self.assertAlmostEqual(haversine_meters(0.0, 0.0, 1.0, 0.0), expected, places=3)

    def test_longitude_shrinks_towards_the_poles(self):
        at_equator = haversine_meters(0.0, 0.0, 0.0, 1.0)
        at_sixty = haversine_meters(60.0, 0.0, 60.0, 1.0)
        self.assertAlmostEqual(at_sixty, at_equator / 2, delta=1.0)

    def test_berlin_to_paris(self):
        # widely quoted as ~878 km
        distance = haversine_meters(52.520008, 13.404954, 48.856614, 2.352222)
        self.assertAlmostEqual(distance / 1000, 878, delta=2)

    def test_is_symmetric(self):
        forward = haversine_meters(52.52, 13.405, 52.53, 13.41)
        backward = haversine_meters(52.53, 13.41, 52.52, 13.405)
        self.assertAlmostEqual(forward, backward)

    def test_one_meter_step_is_resolved(self):
        """The min-distance gate works at metre scale, so small steps must not round away."""
        one_meter_north = 1 / (EARTH_RADIUS_METERS * math.pi / 180)
        self.assertAlmostEqual(haversine_meters(52.52, 13.405, 52.52 + one_meter_north, 13.405), 1.0, places=3)
