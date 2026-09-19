"""Tests for ModemTelemetry."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from v3xctrl_telemetry.dataclasses import ModemState
from v3xctrl_telemetry.ModemTelemetry import ModemTelemetry


def _make_modem(
    *,
    sim_status: str = "OK",
    signal: tuple[int, int] = (-10, -95),
    band: str = "20",
    cell_id: str = "ABC123",
) -> MagicMock:
    modem = MagicMock()
    modem.get_sim_status.return_value = sim_status
    modem.get_signal_quality.return_value = SimpleNamespace(rsrq=signal[0], rsrp=signal[1])
    modem.get_active_band.return_value = band
    modem.get_cell_location.return_value = (None, None, None, cell_id)

    return modem


def test_state_is_populated_when_modem_and_sim_are_present() -> None:
    fake_modem = _make_modem()
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()

    assert telemetry.get_state() == ModemState(rsrq=-10, rsrp=-95, cell_id="ABC123", band="20")
    fake_modem.enable_location_reporting.assert_called_once()


def test_constructor_raises_when_the_device_is_absent() -> None:
    """Device-level failure belongs to the collector, which retries on a backoff."""
    with (
        patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", side_effect=RuntimeError("no serial")),
        pytest.raises(RuntimeError, match="no serial"),
    ):
        ModemTelemetry("/dev/ttyUSB0")


def test_constructor_raises_when_the_sim_status_cannot_be_read() -> None:
    fake_modem = _make_modem()
    fake_modem.get_sim_status.side_effect = RuntimeError("AT timeout")

    with (
        patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem),
        pytest.raises(RuntimeError, match="AT timeout"),
    ):
        ModemTelemetry("/dev/ttyUSB0")


def test_missing_sim_reports_an_empty_state_without_at_queries() -> None:
    fake_modem = _make_modem(sim_status="ABSENT")
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()

    assert telemetry.get_state() == ModemState()
    fake_modem.get_signal_quality.assert_not_called()


def test_sim_is_not_rechecked_before_the_interval_elapses() -> None:
    fake_modem = _make_modem(sim_status="ABSENT")
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        for _ in range(5):
            telemetry.update()

    # Only the check from the constructor
    assert fake_modem.get_sim_status.call_count == 1


def test_state_populates_once_a_sim_appears() -> None:
    fake_modem = _make_modem(sim_status="ABSENT")
    with (
        patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem),
        patch.object(ModemTelemetry, "SIM_RECHECK_INTERVAL_S", 0.0),
    ):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()
        assert telemetry.get_state() == ModemState()

        fake_modem.get_sim_status.return_value = "OK"
        telemetry.update()

    assert telemetry.get_state() == ModemState(rsrq=-10, rsrp=-95, cell_id="ABC123", band="20")


def test_update_raises_when_the_at_session_fails() -> None:
    """A modem that stops answering is the collector's problem, not the source's."""
    fake_modem = _make_modem()
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()

        fake_modem.get_signal_quality.side_effect = RuntimeError("AT timeout")
        with pytest.raises(RuntimeError, match="AT timeout"):
            telemetry.update()


def test_get_state_is_safe_to_call_before_update() -> None:
    fake_modem = _make_modem()
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")

    assert telemetry.get_state() == ModemState()
