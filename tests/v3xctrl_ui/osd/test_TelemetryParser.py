import unittest

from v3xctrl_control.message import Telemetry
from v3xctrl_ui.osd.TelemetryParser import parse_telemetry, TelemetryData


class TestParseTelemetry(unittest.TestCase):
    def test_parse_telemetry_basic(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 3, "id": 0x0A0F},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False}
        })

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
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 1, "id": 0x0100},
            "bat": {"vol": 3200, "avg": 3150, "pct": 20, "wrn": True}
        })

        data = parse_telemetry(telemetry)

        self.assertEqual(data.battery_voltage, "3.20V")
        self.assertEqual(data.battery_average_voltage, "3.15V")
        self.assertEqual(data.battery_percent, "20%")
        self.assertTrue(data.battery_warning)

    def test_parse_telemetry_unknown_cell(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -15, "rsrp": -100},
            "cell": {"band": 7, "id": "?"},
            "bat": {"vol": 4000, "avg": 3950, "pct": 90, "wrn": False}
        })

        data = parse_telemetry(telemetry)

        self.assertEqual(data.signal_band, "BAND 7")
        self.assertEqual(data.signal_cell, "CELL ?")

    def test_parse_telemetry_cell_id_parsing(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 20, "id": 0xFF00},
            "bat": {"vol": 3700, "avg": 3700, "pct": 60, "wrn": False}
        })

        data = parse_telemetry(telemetry)

        self.assertEqual(data.signal_cell, "255:0")

    def test_parse_telemetry_gstreamer_recording(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 3, "id": 0x0100},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            "gst": 0b0001
        })

        data = parse_telemetry(telemetry)

        self.assertTrue(data.recording)

    def test_parse_telemetry_gstreamer_not_recording(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 3, "id": 0x0100},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            "gst": 0b0000
        })

        data = parse_telemetry(telemetry)

        self.assertFalse(data.recording)

    def test_parse_telemetry_services_flags(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 3, "id": 0x0100},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            "svc": 0b0011
        })

        data = parse_telemetry(telemetry)

        self.assertTrue(data.service_video)
        self.assertTrue(data.service_debug)

    def test_parse_telemetry_videocore_flags(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 3, "id": 0x0100},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            "vc": 0xF5
        })

        data = parse_telemetry(telemetry)

        self.assertEqual(data.vc_current_flags, 0x05)
        self.assertEqual(data.vc_history_flags, 0x0F)

    def test_parse_telemetry_missing_optional_fields(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -10, "rsrp": -90},
            "cell": {"band": 3, "id": 0x0100},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False}
        })

        data = parse_telemetry(telemetry)

        self.assertFalse(data.recording)
        self.assertFalse(data.service_video)
        self.assertFalse(data.service_debug)
        self.assertEqual(data.vc_current_flags, 0)
        self.assertEqual(data.vc_history_flags, 0)

    def test_telemetry_data_defaults(self):
        data = TelemetryData()

        self.assertEqual(data.signal_quality, {"rsrq": -1, "rsrp": -1})
        self.assertEqual(data.signal_band, "BAND ?")
        self.assertEqual(data.signal_cell, "CELL ?")
        self.assertEqual(data.battery_icon, 0)
        self.assertEqual(data.battery_voltage, "0.00V")
        self.assertEqual(data.battery_average_voltage, "0.00V")
        self.assertEqual(data.battery_percent, "0%")
        self.assertFalse(data.battery_warning)
        self.assertFalse(data.recording)
        self.assertFalse(data.service_video)
        self.assertFalse(data.service_debug)
        self.assertEqual(data.vc_current_flags, 0)
        self.assertEqual(data.vc_history_flags, 0)


if __name__ == "__main__":
    unittest.main()
