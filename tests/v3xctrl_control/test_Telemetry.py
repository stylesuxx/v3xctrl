import sys
import unittest
from unittest.mock import MagicMock
import threading
import time

# Mock GStreamer before any imports
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['gi.repository.Gst'] = MagicMock()
sys.modules['gi.repository.GLib'] = MagicMock()

# Import the actual Telemetry class and dataclasses
from src.v3xctrl_control.Telemetry import Telemetry
from src.v3xctrl_telemetry import (
    SignalInfo, CellInfo, BatteryInfo, TelemetryPayload
)


class TestTelemetry(unittest.TestCase):
    def test_set_signal_unknown(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(rsrq=0, rsrp=0),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        tel._set_signal_unknown()
        self.assertEqual(tel.payload.sig.rsrq, -1)
        self.assertEqual(tel.payload.sig.rsrp, -1)

    def test_set_cell_unknown(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(band="1"),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        tel._set_cell_unknown()
        self.assertEqual(tel.payload.cell.band, "?")

    def test_update_signal_success(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(rsrq=0, rsrp=0),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        tel._modem = MagicMock()
        tel._modem.get_signal_quality.return_value = MagicMock(rsrq=10, rsrp=20)
        tel._update_signal()
        self.assertEqual(tel.payload.sig.rsrq, 10)
        self.assertEqual(tel.payload.sig.rsrp, 20)

    def test_update_signal_fail(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        tel._modem = MagicMock()
        tel._modem.get_signal_quality.side_effect = Exception("fail")
        tel._set_signal_unknown = MagicMock()
        tel._update_signal()
        tel._set_signal_unknown.assert_called_once()

    def test_update_cell_success(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(band="0"),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        tel._modem = MagicMock()
        tel._modem.get_active_band.return_value = 7
        tel._update_cell()
        self.assertEqual(tel.payload.cell.band, 7)

    def test_update_cell_fail(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(band="1"),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        tel._modem = MagicMock()
        tel._modem.get_active_band.side_effect = Exception("fail")
        tel._set_cell_unknown = MagicMock()
        tel._update_cell()
        tel._set_cell_unknown.assert_called_once()

    def test_update_battery(self):
        from v3xctrl_telemetry.BatteryTelemetry import BatteryState

        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        # Mock battery with get_state() returning BatteryState
        tel._battery = MagicMock()
        tel._battery.get_state.return_value = BatteryState(
            voltage=1,
            average_voltage=2,
            percentage=3,
            warning=True,
            cell_count=3
        )
        tel._update_battery()
        self.assertEqual(tel.payload.bat.vol, 1)
        self.assertEqual(tel.payload.bat.avg, 2)
        self.assertEqual(tel.payload.bat.pct, 3)
        self.assertEqual(tel.payload.bat.wrn, True)

    def test_update_services(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo(),
            svc=0
        )
        tel._services = MagicMock()
        tel._services.update = MagicMock()
        tel._services.get_byte.return_value = 0x01  # v3xctrl_video active
        tel._update_services()
        self.assertEqual(tel.payload.svc, 0x01)

    def test_update_services_fail(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo(),
            svc=0x03  # Set to non-zero initially
        )
        tel._services = MagicMock()
        tel._services.update.side_effect = Exception("fail")
        tel._update_services()
        self.assertEqual(tel.payload.svc, 0)  # Should be reset to 0 on error

    def test_update_videocore(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo(),
            vc=0
        )
        tel._videocore = MagicMock()
        tel._videocore.update = MagicMock()
        tel._videocore.get_byte.return_value = 0x55  # 0101 0101 - current and history flags
        tel._update_videocore()
        self.assertEqual(tel.payload.vc, 0x55)

    def test_update_videocore_fail(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo(),
            vc=0x55  # Set to non-zero initially
        )
        tel._videocore = MagicMock()
        tel._videocore.update.side_effect = Exception("fail")
        tel._update_videocore()
        self.assertEqual(tel.payload.vc, 0)  # Should be reset to 0 on error

    def test_update_gst(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo(),
            gst=0
        )
        tel._gst = MagicMock()
        tel._gst.update = MagicMock()
        tel._gst.get_byte.return_value = 0x03  # recording + udp_overrun
        tel._update_gst()
        self.assertEqual(tel.payload.gst, 0x03)

    def test_update_gst_not_recording(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo(),
            gst=0x01  # Set to 1 initially
        )
        tel._gst = MagicMock()
        tel._gst.update = MagicMock()
        tel._gst.get_byte.return_value = 0x00  # No flags set
        tel._update_gst()
        self.assertEqual(tel.payload.gst, 0x00)

    def test_update_gst_fail(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo(),
            gst=0x01  # Set to non-zero initially
        )
        tel._gst = MagicMock()
        tel._gst.update.side_effect = Exception("fail")
        tel._update_gst()
        self.assertEqual(tel.payload.gst, 0)  # Should be reset to 0 on error

    def test_get_telemetry_returns_dict(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(rsrq=10, rsrp=20),
            cell=CellInfo(id="123", band="7"),
            loc=MagicMock(),
            bat=BatteryInfo(vol=12000, avg=4000, pct=75, wrn=False),
            svc=0x01,
            vc=0x55,
            gst=0x01
        )
        result = tel.get_telemetry()

        # Verify it's a dict
        self.assertIsInstance(result, dict)

        # Verify nested structure
        self.assertEqual(result["sig"]["rsrq"], 10)
        self.assertEqual(result["sig"]["rsrp"], 20)
        self.assertEqual(result["svc"], 0x01)
        self.assertEqual(result["vc"], 0x55)
        self.assertEqual(result["gst"], 0x01)

        # Verify it's a copy (modifying result doesn't affect payload)
        result["sig"]["rsrq"] = 999
        self.assertEqual(tel.payload.sig.rsrq, 10)

    def test_run_and_stop(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel._running = threading.Event()
        tel._interval = 0.01
        tel._modem = MagicMock()
        tel._update_signal = MagicMock()
        tel._update_cell = MagicMock()
        tel._update_battery = MagicMock()
        tel._update_services = MagicMock()
        tel._update_videocore = MagicMock()
        tel._update_gst = MagicMock()
        tel.run = Telemetry.run.__get__(tel)  # bind actual run method
        t = threading.Thread(target=tel.run)
        t.start()
        time.sleep(0.05)
        tel.stop()
        t.join()
        tel._update_signal.assert_called()
        tel._update_cell.assert_called()
        tel._update_battery.assert_called()


if __name__ == "__main__":
    unittest.main()
