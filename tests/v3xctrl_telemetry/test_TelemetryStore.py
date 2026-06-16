"""Tests for TelemetryStore."""

import threading

from v3xctrl_telemetry.BatteryTelemetry import BatteryState
from v3xctrl_telemetry.dataclasses import (
    GpsFixType,
    GstFlags,
    LocationInfo,
    ModemState,
    ServiceFlags,
    ThrottleFlags,
    VideoCoreFlags,
)
from v3xctrl_telemetry.TelemetryStore import TelemetryStore


def test_empty_snapshot_has_default_fields() -> None:
    store = TelemetryStore()
    snapshot = store.get_snapshot()
    assert snapshot["sig"] == {"rsrq": -1, "rsrp": -1}
    assert snapshot["cell"] == {"id": "?", "band": "?"}
    assert snapshot["bat"]["vol"] == 0
    assert snapshot["svc"] == 0
    assert snapshot["vc"] == 0
    assert snapshot["gst"] == 0


def test_update_modem_writes_signal_and_cell() -> None:
    store = TelemetryStore()
    store.update_modem(ModemState(rsrq=-10, rsrp=-95, cell_id="ABC", band="20"))
    snapshot = store.get_snapshot()
    assert snapshot["sig"] == {"rsrq": -10, "rsrp": -95}
    assert snapshot["cell"] == {"id": "ABC", "band": "20"}


def test_update_battery_writes_all_fields() -> None:
    store = TelemetryStore()
    store.update_battery(
        BatteryState(voltage=3800, average_voltage=3850, percentage=72, warning=True, cell_count=1, current=420)
    )
    snapshot = store.get_snapshot()
    assert snapshot["bat"] == {"vol": 3800, "avg": 3850, "pct": 72, "wrn": True, "cur": 420}


def test_update_gps_replaces_location() -> None:
    store = TelemetryStore()
    loc = LocationInfo(lat=52.5, lng=13.4, fix_type=GpsFixType.FIX_3D, speed=12.3, satellites=8)
    store.update_gps(loc)
    snapshot = store.get_snapshot()
    assert snapshot["loc"]["lat"] == 52.5
    assert snapshot["loc"]["lng"] == 13.4
    assert snapshot["loc"]["fix_type"] == GpsFixType.FIX_3D
    assert snapshot["loc"]["satellites"] == 8


def test_update_services_packs_to_byte() -> None:
    store = TelemetryStore()
    store.update_services(ServiceFlags(video=True, reverse_shell=False, debug=True))
    assert store.get_snapshot()["svc"] == 0b101


def test_update_videocore_packs_to_byte() -> None:
    store = TelemetryStore()
    store.update_videocore(
        VideoCoreFlags(
            current=ThrottleFlags(undervolt=True),
            history=ThrottleFlags(throttled=True),
        )
    )
    assert store.get_snapshot()["vc"] == int(
        VideoCoreFlags(current=ThrottleFlags(undervolt=True), history=ThrottleFlags(throttled=True))
    )


def test_update_gst_packs_to_byte() -> None:
    store = TelemetryStore()
    store.update_gst(GstFlags(recording=True, udp_overrun=True))
    assert store.get_snapshot()["gst"] == 0b11


def test_snapshot_is_independent_of_subsequent_writes() -> None:
    store = TelemetryStore()
    store.update_modem(ModemState(rsrq=-10, rsrp=-95, cell_id="ABC", band="20"))
    snapshot = store.get_snapshot()
    store.update_modem(ModemState(rsrq=-5, rsrp=-80, cell_id="XYZ", band="3"))
    assert snapshot["sig"] == {"rsrq": -10, "rsrp": -95}
    assert snapshot["cell"] == {"id": "ABC", "band": "20"}


def test_concurrent_writers_and_readers_dont_corrupt_state() -> None:
    store = TelemetryStore()
    stop = threading.Event()

    def writer_modem() -> None:
        while not stop.is_set():
            store.update_modem(ModemState(rsrq=-10, rsrp=-95, cell_id="A", band="20"))

    def writer_battery() -> None:
        while not stop.is_set():
            store.update_battery(
                BatteryState(
                    voltage=3800, average_voltage=3850, percentage=80, warning=False, cell_count=1, current=100
                )
            )

    def reader() -> None:
        while not stop.is_set():
            snap = store.get_snapshot()
            # consistency: if sig.rsrq is set it should match the writer's value
            assert snap["sig"]["rsrq"] in (-1, -10)
            assert snap["bat"]["vol"] in (0, 3800)

    threads = [
        threading.Thread(target=writer_modem),
        threading.Thread(target=writer_battery),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]
    for t in threads:
        t.start()
    stop_timer = threading.Timer(0.2, stop.set)
    stop_timer.start()
    for t in threads:
        t.join(timeout=2.0)
        assert not t.is_alive()
    stop_timer.cancel()
