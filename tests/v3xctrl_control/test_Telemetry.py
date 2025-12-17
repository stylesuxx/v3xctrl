import unittest
from unittest.mock import MagicMock
import threading
import time

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
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=MagicMock(),
            bat=BatteryInfo()
        )
        tel._battery = MagicMock(voltage=1, average_voltage=2, percentage=3, warning=True)
        tel._battery.update = MagicMock()
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

    def test_get_telemetry_returns_dict(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.payload = TelemetryPayload(
            sig=SignalInfo(rsrq=10, rsrp=20),
            cell=CellInfo(id="123", band="7"),
            loc=MagicMock(),
            bat=BatteryInfo(vol=12000, avg=4000, pct=75, wrn=False),
            svc=0x01,
            vc=0x55
        )
        result = tel.get_telemetry()

        # Verify it's a dict
        self.assertIsInstance(result, dict)

        # Verify nested structure
        self.assertEqual(result["sig"]["rsrq"], 10)
        self.assertEqual(result["sig"]["rsrp"], 20)
        self.assertEqual(result["svc"], 0x01)
        self.assertEqual(result["vc"], 0x55)

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
