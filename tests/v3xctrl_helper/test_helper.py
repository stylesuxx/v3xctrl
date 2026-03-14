import unittest

from v3xctrl_helper.helper import color_to_hex, is_int


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
