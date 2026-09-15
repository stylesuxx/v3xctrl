import unittest
from dataclasses import FrozenInstanceError

from v3xctrl_tcp import Transport
from v3xctrl_ui.core.SettingsSchema import (
    DEFAULT_TRANSPORT,
    PortSettings,
    RelaySettings,
    TimingSettings,
    coerce,
)

SCHEMA_LOGGER = "v3xctrl_ui.core.SettingsSchema"


class TestCoerce(unittest.TestCase):
    def test_a_matching_value_is_kept(self):
        self.assertEqual(coerce("ports.video", 9999, 16384), 9999)
        self.assertEqual(coerce("relay.server", "example.com", "default.com"), "example.com")
        self.assertEqual(coerce("relay.enabled", True, False), True)

    def test_a_mismatched_value_falls_back_to_the_default(self):
        with self.assertLogs(SCHEMA_LOGGER, level="WARNING"):
            self.assertEqual(coerce("ports.video", "banana", 16384), 16384)

    def test_the_warning_names_the_key_and_the_value(self):
        with self.assertLogs(SCHEMA_LOGGER, level="WARNING") as logged:
            coerce("ports.video", "banana", 16384)

        message = logged.output[0]
        self.assertIn("ports.video", message)
        self.assertIn("banana", message)

    def test_a_flag_is_not_accepted_where_a_number_belongs(self):
        """bool subclasses int, so True would otherwise pass as 1."""
        with self.assertLogs(SCHEMA_LOGGER, level="WARNING"):
            self.assertEqual(coerce("ports.video", True, 16384), 16384)

    def test_a_number_is_not_accepted_where_a_flag_belongs(self):
        """The other half of the bool/int overlap: a bool default must not fall through to int."""
        with self.assertLogs(SCHEMA_LOGGER, level="WARNING"):
            self.assertEqual(coerce("relay.enabled", 5, False), False)

    def test_a_known_enum_member_is_parsed(self):
        self.assertEqual(coerce("transport", "tcp", DEFAULT_TRANSPORT), Transport.TCP)

    def test_an_unknown_enum_member_falls_back(self):
        with self.assertLogs(SCHEMA_LOGGER, level="WARNING") as logged:
            self.assertEqual(coerce("transport", "quic", DEFAULT_TRANSPORT), Transport.UDP)

        self.assertIn("quic", logged.output[0])


class TestSectionParsing(unittest.TestCase):
    def test_missing_keys_come_from_the_defaults(self):
        ports = PortSettings.from_raw({})

        self.assertEqual(ports.video, 16384)
        self.assertEqual(ports.control, 16386)

    def test_present_keys_override_the_defaults(self):
        ports = PortSettings.from_raw({"video": 9999})

        self.assertEqual(ports.video, 9999)
        self.assertEqual(ports.control, 16386)

    def test_an_unknown_key_is_ignored(self):
        ports = PortSettings.from_raw({"video": 9999, "carrier_pigeon": True})

        self.assertEqual(ports.video, 9999)
        self.assertFalse(hasattr(ports, "carrier_pigeon"))

    def test_one_bad_key_does_not_take_the_rest_of_the_section_with_it(self):
        with self.assertLogs(SCHEMA_LOGGER, level="WARNING"):
            ports = PortSettings.from_raw({"video": "banana", "control": 9999})

        self.assertEqual(ports.video, 16384)
        self.assertEqual(ports.control, 9999)

    def test_every_section_parses_from_an_empty_table(self):
        for section_type in (PortSettings, RelaySettings, TimingSettings):
            with self.subTest(section=section_type.NAME):
                self.assertEqual(section_type.from_raw({}), section_type())


class TestSectionValues(unittest.TestCase):
    def test_a_section_is_frozen(self):
        ports = PortSettings()

        with self.assertRaises(FrozenInstanceError):
            ports.video = 1

    def test_sections_compare_by_value(self):
        self.assertEqual(PortSettings(video=1), PortSettings(video=1))
        self.assertNotEqual(PortSettings(video=1), PortSettings(video=2))

    def test_to_raw_round_trips(self):
        relay = RelaySettings(enabled=True, server="example.com:1", id="abc", spectator_mode=True)

        self.assertEqual(RelaySettings.from_raw(relay.to_raw()), relay)

    def test_to_raw_covers_every_field(self):
        raw = TimingSettings().to_raw()

        self.assertEqual(set(raw), {"main_loop_fps", "control_update_hz", "latency_check_hz"})


if __name__ == "__main__":
    unittest.main()
