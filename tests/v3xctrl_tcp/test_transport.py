import unittest
from enum import StrEnum

from v3xctrl_tcp.transport import Transport


class TestTransportEnum(unittest.TestCase):
    def test_udp_value(self):
        self.assertEqual(Transport.UDP.value, "udp")

    def test_tcp_value(self):
        self.assertEqual(Transport.TCP.value, "tcp")

    def test_string_equality_udp(self):
        self.assertEqual(Transport.UDP, "udp")

    def test_string_equality_tcp(self):
        self.assertEqual(Transport.TCP, "tcp")

    def test_membership_valid(self):
        self.assertIn("udp", Transport.__members__.values())
        self.assertIn("tcp", Transport.__members__.values())

    def test_membership_invalid(self):
        with self.assertRaises(ValueError):
            Transport("websocket")

    def test_iteration_returns_all_members(self):
        members = list(Transport)
        self.assertEqual(len(members), 2)
        self.assertIn(Transport.UDP, members)
        self.assertIn(Transport.TCP, members)

    def test_is_str_enum(self):
        self.assertIsInstance(Transport.UDP, StrEnum)
        self.assertIsInstance(Transport.TCP, StrEnum)

    def test_is_str(self):
        self.assertIsInstance(Transport.UDP, str)
        self.assertIsInstance(Transport.TCP, str)

    def test_can_use_as_string(self):
        self.assertTrue(Transport.UDP.startswith("u"))
        self.assertTrue(Transport.TCP.upper() == "TCP")

    def test_lookup_by_value(self):
        self.assertIs(Transport("udp"), Transport.UDP)
        self.assertIs(Transport("tcp"), Transport.TCP)

    def test_lookup_by_name(self):
        self.assertIs(Transport["UDP"], Transport.UDP)
        self.assertIs(Transport["TCP"], Transport.TCP)


if __name__ == "__main__":
    unittest.main()
