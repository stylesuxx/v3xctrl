import unittest

from v3xctrl_control.message import Telemetry
from v3xctrl_ui.core.dataclasses import GpsFixType
from v3xctrl_ui.core.TelemetryParser import TelemetryData, parse_telemetry


class TestParseTelemetry(unittest.TestCase):
    def test_parse_telemetry_basic(self):
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 3, "id": 0x0A0F},
                "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.signal_quality["rsrq"], -10)
        self.assertEqual(data.signal_quality["rsrp"], -90)
        self.assertEqual(data.signal_band, "BAND 3")
        self.assertEqual(data.signal_cell, "10:15")
        self.assertEqual(data.battery_voltage, "3.80V")
        self.assertEqual(data.battery_average_voltage, "3.75V")
        self.assertEqual(data.battery_percent, "75%")
        self.assertEqual(data.battery_icon, 75)
        self.assertFalse(data.battery_warning)

    def test_parse_telemetry_battery_warning(self):
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 1, "id": 0x0100},
                "bat": {"vol": 3200, "avg": 3150, "pct": 20, "wrn": True},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.battery_voltage, "3.20V")
        self.assertEqual(data.battery_average_voltage, "3.15V")
        self.assertEqual(data.battery_percent, "20%")
        self.assertTrue(data.battery_warning)

    def test_parse_telemetry_unknown_cell(self):
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -15, "rsrp": -100},
                "cell": {"band": 7, "id": "?"},
                "bat": {"vol": 4000, "avg": 3950, "pct": 90, "wrn": False},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.signal_band, "BAND 7")
        self.assertEqual(data.signal_cell, "CELL ?")

    def test_parse_telemetry_cell_id_parsing(self):
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 20, "id": 0xFF00},
                "bat": {"vol": 3700, "avg": 3700, "pct": 60, "wrn": False},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.signal_cell, "255:0")

    def test_parse_telemetry_missing_optional_fields(self):
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 3, "id": 0x0100},
                "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.gps_fix_type, GpsFixType.NO_HARDWARE)
        self.assertEqual(data.gps_speed, 0.0)
        self.assertEqual(data.gps_satellites, "0 SAT")

    def test_telemetry_data_defaults(self):
        data = TelemetryData()

        self.assertEqual(data.signal_quality, {"rsrq": -1, "rsrp": -1})
        self.assertEqual(data.signal_band, "BAND ?")
        self.assertEqual(data.signal_cell, "CELL ?")
        self.assertEqual(data.battery_icon, 0)
        self.assertEqual(data.battery_voltage, "0.00V")
        self.assertEqual(data.battery_average_voltage, "0.00V")
        self.assertEqual(data.battery_percent, "0%")
        self.assertEqual(data.battery_current, "0mA")
        self.assertFalse(data.battery_warning)

    def test_parse_telemetry_battery_current_milliamps(self):
        """Test battery current parsing for values under 1000mA."""
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 3, "id": 0x0100},
                "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False, "cur": 500},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.battery_current, "500mA")

    def test_parse_telemetry_battery_current_amps(self):
        """Test battery current parsing for values >= 1000mA (displayed as A)."""
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 3, "id": 0x0100},
                "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False, "cur": 2500},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.battery_current, "2.50A")

    def test_parse_telemetry_battery_current_exactly_1000(self):
        """Test battery current parsing at exactly 1000mA threshold."""
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 3, "id": 0x0100},
                "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False, "cur": 1000},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.battery_current, "1.00A")

    def test_parse_telemetry_battery_current_missing(self):
        """Test battery current defaults to 0mA when not in telemetry."""
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -10, "rsrp": -90},
                "cell": {"band": 3, "id": 0x0100},
                "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            }
        )

        data = parse_telemetry(telemetry)

        self.assertEqual(data.battery_current, "0mA")


if __name__ == "__main__":
    unittest.main()
