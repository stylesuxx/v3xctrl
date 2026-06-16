"""Tests for ModemTelemetry."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


def test_initial_state_when_modem_present() -> None:
    fake_modem = _make_modem()
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()

    assert telemetry.get_state() == ModemState(rsrq=-10, rsrp=-95, cell_id="ABC123", band="20")


def test_state_default_when_modem_init_fails() -> None:
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", side_effect=RuntimeError("no serial")):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()

    assert telemetry.get_state() == ModemState()


def test_state_default_when_no_sim() -> None:
    fake_modem = _make_modem(sim_status="ABSENT")
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()

    assert telemetry.get_state() == ModemState()


def test_recovers_after_transient_read_failure() -> None:
    fake_modem = _make_modem()
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()
        assert telemetry.get_state().rsrq == -10

        fake_modem.get_signal_quality.side_effect = RuntimeError("AT timeout")
        telemetry.update()
        assert telemetry.get_state() == ModemState()
        assert telemetry._modem is None  # dropped to force re-init

        fake_modem.get_signal_quality.side_effect = None
        fake_modem.get_signal_quality.return_value = SimpleNamespace(rsrq=-5, rsrp=-80)
        telemetry.update()
        assert telemetry.get_state().rsrq == -5
        assert telemetry.get_state().rsrp == -80


def test_sim_absent_skips_init_for_recheck_interval() -> None:
    fake_modem = _make_modem(sim_status="ABSENT")
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem) as factory:
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        # First init attempt happened in __init__
        assert factory.call_count == 1

        # Burn the recheck interval - 1 calls without retrying
        for _ in range(ModemTelemetry.SIM_RECHECK_INTERVAL - 1):
            telemetry.update()
        assert factory.call_count == 1

        # Next update should trigger another init attempt
        telemetry.update()
        assert factory.call_count == 2


def test_sim_recovery_clears_absent_flag() -> None:
    fake_modem = _make_modem(sim_status="ABSENT")
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", return_value=fake_modem):
        telemetry = ModemTelemetry("/dev/ttyUSB0")

        # SIM appears
        fake_modem.get_sim_status.return_value = "OK"
        for _ in range(ModemTelemetry.SIM_RECHECK_INTERVAL):
            telemetry.update()

        # After the recheck attempt fires, signal should populate
        assert telemetry.get_state().rsrq == -10


def test_get_state_is_safe_to_call_before_update() -> None:
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", side_effect=RuntimeError("no modem")):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
    assert telemetry.get_state() == ModemState()


def test_update_never_raises_even_on_init_failure() -> None:
    with patch("v3xctrl_telemetry.ModemTelemetry.AIR780EU", side_effect=RuntimeError("hardware gone")):
        telemetry = ModemTelemetry("/dev/ttyUSB0")
        telemetry.update()  # must not raise
        telemetry.update()
        assert telemetry.get_state() == ModemState()
