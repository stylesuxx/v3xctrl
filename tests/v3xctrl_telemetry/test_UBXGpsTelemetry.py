"""Tests for UBXGpsTelemetry."""

import unittest
from unittest.mock import MagicMock, patch

from pytest import approx

from v3xctrl_telemetry.dataclasses import GpsFixType
from v3xctrl_telemetry.UBXGpsTelemetry import UBXGpsTelemetry, UBXMessageId

_MODULE = "v3xctrl_telemetry.UBXGpsTelemetry"

# Matches the desired config produced by UBXGpsTelemetry(rate_hz=5)
_MATCHING_CONFIG = {
    "CFG_UART1OUTPROT_UBX": 1,
    "CFG_UART1OUTPROT_NMEA": 0,
    "CFG_MSGOUT_UBX_NAV_PVT_UART1": 1,
    "CFG_RATE_MEAS": 200,  # 1000 // 5
}


def _make_message(identity, **attrs):
    msg = MagicMock()
    msg.identity = identity
    for key, value in attrs.items():
        setattr(msg, key, value)
    return msg


def _make_gps(rate_hz=5):
    """Create a GPS instance with _configure_module and UBXReader mocked out."""
    mock_port = MagicMock()
    mock_port.in_waiting = 0
    mock_reader = MagicMock()
    with (
        patch.object(UBXGpsTelemetry, "_configure_module", return_value=mock_port),
        patch(f"{_MODULE}.UBXReader", return_value=mock_reader),
    ):
        gps = UBXGpsTelemetry(rate_hz=rate_hz)
    return gps, mock_port, mock_reader


def _read_once(mock_port, msg):
    """Return a side_effect that delivers msg once then sets in_waiting=0 to stop the loop."""

    def side_effect():
        mock_port.in_waiting = 0
        return (None, msg)

    return side_effect


class TestUpdate(unittest.TestCase):
    def test_no_pending_data_returns_false(self):
        gps, mock_port, _ = _make_gps()
        mock_port.in_waiting = 0

        assert gps.update() is False

    def test_nav_pvt_3d_fix_updates_state(self):
        gps, mock_port, mock_reader = _make_gps()
        msg = _make_message(
            UBXMessageId.NAV_PVT,
            fixType=3,
            lat=51.5,
            lon=-0.1,
            gSpeed=5000,  # mm/s → 5000 * 3.6 / 1000 = 18 km/h
            numSV=10,
        )
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, msg)

        result = gps.update()

        assert result is True
        state = gps.get_state()
        assert state.fix_type == GpsFixType.FIX_3D
        assert state.lat == 51.5
        assert state.lng == -0.1
        assert state.satellites == 10
        assert state.speed == approx(18.0)

    def test_nav_pvt_2d_fix_updates_position(self):
        gps, mock_port, mock_reader = _make_gps()
        msg = _make_message(UBXMessageId.NAV_PVT, fixType=2, lat=48.8, lon=2.3, gSpeed=0, numSV=5)
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, msg)

        gps.update()

        state = gps.get_state()
        assert state.fix_type == GpsFixType.FIX_2D
        assert state.lat == 48.8

    def test_nav_pvt_no_fix_does_not_update_position(self):
        gps, mock_port, mock_reader = _make_gps()
        msg = _make_message(UBXMessageId.NAV_PVT, fixType=0, numSV=3)
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, msg)

        gps.update()

        state = gps.get_state()
        assert state.fix_type == GpsFixType.NO_FIX
        assert state.lat == 0.0
        assert state.lng == 0.0

    def test_nav_pvt_dead_reckoning_does_not_update_position(self):
        gps, mock_port, mock_reader = _make_gps()
        msg = _make_message(UBXMessageId.NAV_PVT, fixType=1, numSV=0)
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, msg)

        gps.update()

        state = gps.get_state()
        assert state.fix_type == GpsFixType.DEAD_RECKONING
        assert state.lat == 0.0  # DEAD_RECKONING < FIX_2D, position not updated

    def test_nav_pvt_invalid_fix_type_defaults_to_no_fix(self):
        gps, mock_port, mock_reader = _make_gps()
        msg = _make_message(UBXMessageId.NAV_PVT, fixType=99, numSV=0)
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, msg)

        gps.update()

        assert gps.get_state().fix_type == GpsFixType.NO_FIX

    def test_inf_message_logs_warning_and_returns_false(self):
        gps, mock_port, mock_reader = _make_gps()
        msg = _make_message("INF-NOTICE", msgContent="hello from module")
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, msg)

        assert gps.update() is False

    def test_non_nav_pvt_message_returns_false(self):
        gps, mock_port, mock_reader = _make_gps()
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, _make_message("CFG-VALGET"))

        assert gps.update() is False

    def test_none_message_is_skipped(self):
        gps, mock_port, mock_reader = _make_gps()
        mock_port.in_waiting = 1
        mock_reader.read.side_effect = _read_once(mock_port, None)

        assert gps.update() is False


class TestOpenAtBaud(unittest.TestCase):
    def setUp(self):
        self.gps, _, _ = _make_gps()

    def test_ubx_sync_found_returns_port(self):
        mock_port = MagicMock()
        mock_port.read.return_value = b"\xb5\x62" + b"\x00" * 254

        with patch(f"{_MODULE}.serial.Serial", return_value=mock_port):
            result = self.gps._open_at_baud(115200)

        assert result is mock_port

    def test_no_ubx_sync_closes_and_returns_none(self):
        mock_port = MagicMock()
        mock_port.read.return_value = b"\x00" * 256

        with patch(f"{_MODULE}.serial.Serial", return_value=mock_port):
            result = self.gps._open_at_baud(9600)

        assert result is None
        mock_port.close.assert_called_once()

    def test_exception_closes_and_returns_none(self):
        mock_port = MagicMock()
        mock_port.read.side_effect = OSError("no device")

        with patch(f"{_MODULE}.serial.Serial", return_value=mock_port):
            result = self.gps._open_at_baud(115200)

        assert result is None
        mock_port.close.assert_called_once()


class TestPollConfig(unittest.TestCase):
    def setUp(self):
        self.gps, _, _ = _make_gps()

    def test_cfg_valget_received_returns_config(self):
        mock_port = MagicMock()
        cfg_msg = _make_message(
            UBXMessageId.CFG_VALGET,
            CFG_UART1OUTPROT_UBX=1,
            CFG_UART1OUTPROT_NMEA=0,
            CFG_MSGOUT_UBX_NAV_PVT_UART1=1,
            CFG_RATE_MEAS=200,
        )
        mock_reader = MagicMock()
        mock_reader.read.return_value = (None, cfg_msg)

        with patch(f"{_MODULE}.UBXReader", return_value=mock_reader), patch(f"{_MODULE}.UBXMessage"):
            result = self.gps._poll_config(mock_port, 115200)

        assert result is not None
        assert result["CFG_UART1OUTPROT_UBX"] == 1
        assert result["CFG_RATE_MEAS"] == 200

    def test_none_message_skipped_then_cfg_valget_returns_config(self):
        mock_port = MagicMock()
        cfg_msg = _make_message(
            UBXMessageId.CFG_VALGET,
            CFG_UART1OUTPROT_UBX=1,
            CFG_UART1OUTPROT_NMEA=0,
            CFG_MSGOUT_UBX_NAV_PVT_UART1=1,
            CFG_RATE_MEAS=200,
        )
        mock_reader = MagicMock()
        mock_reader.read.side_effect = [(None, None), (None, cfg_msg)]

        with patch(f"{_MODULE}.UBXReader", return_value=mock_reader), patch(f"{_MODULE}.UBXMessage"):
            result = self.gps._poll_config(mock_port, 115200)

        assert result is not None
        assert result["CFG_UART1OUTPROT_UBX"] == 1

    def test_missing_key_in_cfg_valget_excluded_from_result(self):
        mock_port = MagicMock()
        cfg_msg = _make_message(UBXMessageId.CFG_VALGET)
        cfg_msg.CFG_UART1OUTPROT_UBX = 1
        cfg_msg.CFG_UART1OUTPROT_NMEA = 0
        cfg_msg.CFG_MSGOUT_UBX_NAV_PVT_UART1 = None
        cfg_msg.CFG_RATE_MEAS = 200
        mock_reader = MagicMock()
        mock_reader.read.return_value = (None, cfg_msg)

        with patch(f"{_MODULE}.UBXReader", return_value=mock_reader), patch(f"{_MODULE}.UBXMessage"):
            result = self.gps._poll_config(mock_port, 115200)

        assert result is not None
        assert "CFG_MSGOUT_UBX_NAV_PVT_UART1" not in result

    def test_non_cfg_valget_message_ignored(self):
        mock_port = MagicMock()
        cfg_msg = _make_message(UBXMessageId.CFG_VALGET, **{k: 1 for k in _MATCHING_CONFIG})
        mock_reader = MagicMock()
        mock_reader.read.side_effect = [
            (None, _make_message(UBXMessageId.NAV_PVT)),
            (None, cfg_msg),
        ]

        with patch(f"{_MODULE}.UBXReader", return_value=mock_reader), patch(f"{_MODULE}.UBXMessage"):
            result = self.gps._poll_config(mock_port, 115200)

        assert result is not None

    def test_deadline_expired_returns_none(self):
        mock_port = MagicMock()
        mock_reader = MagicMock()

        with (
            patch(f"{_MODULE}.UBXReader", return_value=mock_reader),
            patch(f"{_MODULE}.UBXMessage"),
            patch(f"{_MODULE}.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 10.0]
            result = self.gps._poll_config(mock_port, 115200)

        assert result is None

    def test_exception_returns_none(self):
        mock_port = MagicMock()
        mock_port.write.side_effect = OSError("write error")

        with patch(f"{_MODULE}.UBXReader"), patch(f"{_MODULE}.UBXMessage"):
            result = self.gps._poll_config(mock_port, 115200)

        assert result is None


class TestNeedsUpdate(unittest.TestCase):
    def setUp(self):
        self.gps, _, _ = _make_gps()

    def test_matching_config_returns_empty_set(self):
        assert self.gps._needs_update(_MATCHING_CONFIG) == set()

    def test_mismatched_values_returns_affected_keys(self):
        current = {**_MATCHING_CONFIG, "CFG_UART1OUTPROT_UBX": 0, "CFG_UART1OUTPROT_NMEA": 1}
        mismatches = self.gps._needs_update(current)

        assert "CFG_UART1OUTPROT_UBX" in mismatches
        assert "CFG_UART1OUTPROT_NMEA" in mismatches
        assert "CFG_MSGOUT_UBX_NAV_PVT_UART1" not in mismatches

    def test_empty_config_reports_all_keys_as_mismatched(self):
        assert len(self.gps._needs_update({})) == len(self.gps._desired_config)


class TestWriteConfig(unittest.TestCase):
    def setUp(self):
        self.gps, _, _ = _make_gps()

    def test_ack_ack_returns_true(self):
        mock_port = MagicMock()
        mock_reader = MagicMock()
        mock_reader.read.return_value = (None, _make_message(UBXMessageId.ACK_ACK))

        with patch(f"{_MODULE}.UBXReader", return_value=mock_reader), patch(f"{_MODULE}.UBXMessage"):
            assert self.gps._write_config(mock_port) is True

    def test_ack_nak_returns_false(self):
        mock_port = MagicMock()
        mock_reader = MagicMock()
        mock_reader.read.return_value = (None, _make_message(UBXMessageId.ACK_NAK))

        with patch(f"{_MODULE}.UBXReader", return_value=mock_reader), patch(f"{_MODULE}.UBXMessage"):
            assert self.gps._write_config(mock_port) is False

    def test_no_ack_after_all_attempts_returns_false(self):
        mock_port = MagicMock()
        mock_reader = MagicMock()
        mock_reader.read.return_value = (None, None)

        with patch(f"{_MODULE}.UBXReader", return_value=mock_reader), patch(f"{_MODULE}.UBXMessage"):
            assert self.gps._write_config(mock_port) is False


class TestConfigureModule(unittest.TestCase):
    def test_config_already_correct_no_write(self):
        mock_port = MagicMock()
        with (
            patch.object(UBXGpsTelemetry, "_open_at_baud", return_value=mock_port),
            patch.object(UBXGpsTelemetry, "_poll_config", return_value=_MATCHING_CONFIG),
            patch.object(UBXGpsTelemetry, "_write_config") as mock_write,
            patch(f"{_MODULE}.UBXReader"),
        ):
            gps = UBXGpsTelemetry()

        assert gps._serial is mock_port
        mock_write.assert_not_called()

    def test_config_mismatch_triggers_write(self):
        mock_port = MagicMock()
        mismatched = {**_MATCHING_CONFIG, "CFG_UART1OUTPROT_UBX": 0}
        with (
            patch.object(UBXGpsTelemetry, "_open_at_baud", return_value=mock_port),
            patch.object(UBXGpsTelemetry, "_poll_config", return_value=mismatched),
            patch.object(UBXGpsTelemetry, "_write_config") as mock_write,
            patch(f"{_MODULE}.UBXReader"),
        ):
            UBXGpsTelemetry()

        mock_write.assert_called_once_with(mock_port)

    def test_poll_config_none_returns_port_without_write(self):
        mock_port = MagicMock()
        with (
            patch.object(UBXGpsTelemetry, "_open_at_baud", return_value=mock_port),
            patch.object(UBXGpsTelemetry, "_poll_config", return_value=None),
            patch.object(UBXGpsTelemetry, "_write_config") as mock_write,
            patch(f"{_MODULE}.UBXReader"),
        ):
            gps = UBXGpsTelemetry()

        assert gps._serial is mock_port
        mock_write.assert_not_called()

    def test_first_baud_failure_tries_second(self):
        mock_port = MagicMock()
        with (
            patch.object(UBXGpsTelemetry, "_open_at_baud", side_effect=[None, mock_port]) as mock_open,
            patch.object(UBXGpsTelemetry, "_poll_config", return_value=_MATCHING_CONFIG),
            patch(f"{_MODULE}.UBXReader"),
        ):
            gps = UBXGpsTelemetry()

        assert mock_open.call_count == 2
        assert gps._serial is mock_port

    def test_all_bauds_fail_opens_fallback_at_9600(self):
        mock_fallback = MagicMock()
        with (
            patch.object(UBXGpsTelemetry, "_open_at_baud", return_value=None),
            patch(f"{_MODULE}.serial.Serial", return_value=mock_fallback),
            patch(f"{_MODULE}.UBXReader"),
        ):
            gps = UBXGpsTelemetry()

        assert gps._serial is mock_fallback


class TestDefaultState(unittest.TestCase):
    def test_initial_fix_type_is_no_hardware(self):
        gps, _, _ = _make_gps()
        assert gps.get_state().fix_type == GpsFixType.NO_HARDWARE

    def test_initial_position_speed_satellites_are_zero(self):
        gps, _, _ = _make_gps()
        state = gps.get_state()
        assert state.lat == 0.0
        assert state.lng == 0.0
        assert state.speed == 0.0
        assert state.satellites == 0


if __name__ == "__main__":
    unittest.main()
