import unittest
from unittest.mock import patch, MagicMock
import threading
import time

# Import the actual Telemetry class
from src.v3xctrl_control.Telemetry import Telemetry


class TestTelemetry(unittest.TestCase):
    def test_set_signal_unknown(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"sig": {"rsrq": 0, "rsrp": 0}}
        tel._set_signal_unknown()
        self.assertEqual(tel.telemetry["sig"], {"rsrq": -1, "rsrp": -1})

    def test_set_cell_unknown(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"cell": {"band": 1}}
        tel._set_cell_unknown()
        self.assertEqual(tel.telemetry["cell"]["band"], 0)

    def test_update_signal_success(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"sig": {"rsrq": 0, "rsrp": 0}}
        tel._modem = MagicMock()
        tel._modem.get_signal_quality.return_value = MagicMock(rsrq=10, rsrp=20)
        tel._update_signal()
        self.assertEqual(tel.telemetry["sig"], {"rsrq": 10, "rsrp": 20})

    def test_update_signal_fail(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"sig": {"rsrq": 0, "rsrp": 0}}
        tel._modem = MagicMock()
        tel._modem.get_signal_quality.side_effect = Exception("fail")
        tel._set_signal_unknown = MagicMock()
        tel._update_signal()
        tel._set_signal_unknown.assert_called_once()

    def test_update_cell_success(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"cell": {"band": 0}}
        tel._modem = MagicMock()
        tel._modem.get_active_band.return_value = 7
        tel._update_cell()
        self.assertEqual(tel.telemetry["cell"]["band"], 7)

    def test_update_cell_fail(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"cell": {"band": 1}}
        tel._modem = MagicMock()
        tel._modem.get_active_band.side_effect = Exception("fail")
        tel._set_cell_unknown = MagicMock()
        tel._update_cell()
        tel._set_cell_unknown.assert_called_once()

    def test_update_battery(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"bat": {}}
        tel._battery = MagicMock(voltage=1, average_voltage=2, percentage=3, warning=True)
        tel._battery.update = MagicMock()
        tel._update_battery()
        self.assertEqual(
            tel.telemetry["bat"],
            {"vol": 1, "avg": 2, "pct": 3, "wrn": True},
        )

    def test_get_telemetry_returns_copy(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel.telemetry = {"a": 1}
        result = tel.get_telemetry()
        self.assertEqual(result, {"a": 1})
        result["a"] = 2
        self.assertEqual(tel.telemetry, {"a": 1})

    def test_run_and_stop(self):
        tel = Telemetry.__new__(Telemetry)
        tel._lock = threading.Lock()
        tel._running = threading.Event()
        tel._interval = 0.01
        tel._modem = MagicMock()
        tel._update_signal = MagicMock()
        tel._update_cell = MagicMock()
        tel._update_battery = MagicMock()
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
