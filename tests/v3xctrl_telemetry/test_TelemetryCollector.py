"""Tests for TelemetryCollector."""

import threading
import time
from typing import Any
from unittest.mock import MagicMock

from v3xctrl_telemetry.TelemetryCollector import TelemetryCollector


class FakeSource:
    def __init__(self, state: Any = None) -> None:
        self.update_count = 0
        self._state = state if state is not None else "ok"

    def update(self) -> None:
        self.update_count += 1

    def get_state(self) -> Any:
        return self._state


class FailingSource:
    def __init__(self) -> None:
        self.update_count = 0

    def update(self) -> None:
        self.update_count += 1
        raise RuntimeError("source failed")

    def get_state(self) -> Any:  # pragma: no cover - never reached
        return None


def _drain_collector(collector: TelemetryCollector, *, runtime_s: float = 0.15) -> None:
    collector.start()
    time.sleep(runtime_s)
    collector.stop()
    collector.join(timeout=1.0)
    assert not collector.is_alive()


def test_collector_calls_update_and_store_updater() -> None:
    source = FakeSource(state="snapshot")
    updates: list[Any] = []
    collector = TelemetryCollector("fake", source, updates.append, interval=0.02)

    _drain_collector(collector)

    assert source.update_count >= 3
    assert updates and all(state == "snapshot" for state in updates)


def test_collector_survives_source_exceptions() -> None:
    source = FailingSource()
    updates: list[Any] = []
    collector = TelemetryCollector("failing", source, updates.append, interval=0.02)

    _drain_collector(collector)

    assert source.update_count >= 3
    assert updates == []


def test_collector_survives_store_updater_exceptions() -> None:
    source = FakeSource(state="snapshot")
    call_count = 0

    def bad_updater(state: Any) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("store updater failed")

    collector = TelemetryCollector("bad-updater", source, bad_updater, interval=0.02)
    _drain_collector(collector)
    assert call_count >= 3


def test_collector_stop_returns_quickly_even_with_long_interval() -> None:
    source = FakeSource()
    collector = TelemetryCollector("slow", source, lambda _state: None, interval=10.0)
    collector.start()
    time.sleep(0.05)
    t0 = time.monotonic()
    collector.stop()
    collector.join(timeout=1.0)
    elapsed = time.monotonic() - t0
    assert not collector.is_alive()
    assert elapsed < 0.5, f"stop did not return promptly (elapsed={elapsed:.3f}s)"


def test_collector_is_daemon_thread() -> None:
    collector = TelemetryCollector("dm", FakeSource(), lambda _state: None, interval=1.0)
    assert collector.daemon is True


def test_collector_passes_state_to_updater() -> None:
    source = MagicMock()
    source.update = MagicMock()
    source.get_state = MagicMock(return_value={"key": "value"})

    received: list[Any] = []
    collector = TelemetryCollector("mock", source, received.append, interval=0.02)
    _drain_collector(collector)

    assert source.update.call_count >= 3
    assert {"key": "value"} in received


def test_collector_respects_interval_approximately() -> None:
    """At a 50ms interval over 200ms we expect roughly 4 updates, give or take."""
    source = FakeSource()
    collector = TelemetryCollector("rate", source, lambda _state: None, interval=0.05)

    collector.start()
    time.sleep(0.2)
    collector.stop()
    collector.join(timeout=1.0)

    # Loose bound - timing on CI varies, but we should land in [2, 8] for 200ms / 50ms.
    assert 2 <= source.update_count <= 8, f"unexpected update count: {source.update_count}"


def test_multiple_collectors_run_independently() -> None:
    source_a = FakeSource("A")
    source_b = FakeSource("B")
    updates_a: list[Any] = []
    updates_b: list[Any] = []

    collector_a = TelemetryCollector("a", source_a, updates_a.append, interval=0.02)
    collector_b = TelemetryCollector("b", source_b, updates_b.append, interval=0.02)

    collector_a.start()
    collector_b.start()
    time.sleep(0.15)
    collector_a.stop()
    collector_b.stop()
    collector_a.join(timeout=1.0)
    collector_b.join(timeout=1.0)

    assert source_a.update_count >= 3
    assert source_b.update_count >= 3
    assert all(state == "A" for state in updates_a)
    assert all(state == "B" for state in updates_b)


def test_collector_thread_name_includes_source() -> None:
    collector = TelemetryCollector("battery", FakeSource(), lambda _state: None, interval=1.0)
    assert "battery" in collector.name


def test_stop_is_idempotent() -> None:
    collector = TelemetryCollector("idem", FakeSource(), lambda _state: None, interval=0.05)
    collector.start()
    time.sleep(0.05)
    collector.stop()
    collector.stop()  # second call should not raise
    collector.join(timeout=1.0)
    assert not collector.is_alive()


def test_stop_before_start_does_not_block() -> None:
    collector = TelemetryCollector("never", FakeSource(), lambda _state: None, interval=1.0)
    collector.stop()
    assert not collector.is_alive()


def test_collector_does_not_call_update_after_stop() -> None:
    source = FakeSource()
    collector = TelemetryCollector("post-stop", source, lambda _state: None, interval=0.02)

    collector.start()
    time.sleep(0.1)
    collector.stop()
    collector.join(timeout=1.0)

    final_count = source.update_count
    time.sleep(0.1)
    assert source.update_count == final_count


def test_get_state_exception_does_not_call_updater() -> None:
    source = MagicMock()
    source.update = MagicMock()
    source.get_state = MagicMock(side_effect=RuntimeError("state read failed"))

    updater = MagicMock()
    collector = TelemetryCollector("flaky-state", source, updater, interval=0.02)
    _drain_collector(collector)

    assert source.update.call_count >= 3
    assert updater.call_count == 0


def test_concurrent_collectors_do_not_deadlock() -> None:
    """Spin up several collectors writing to a shared list and verify they all finish."""
    sources = [FakeSource(state=i) for i in range(5)]
    lock = threading.Lock()
    updates: list[Any] = []

    def make_updater() -> Any:
        def updater(state: Any) -> None:
            with lock:
                updates.append(state)

        return updater

    collectors = [TelemetryCollector(f"c{i}", sources[i], make_updater(), interval=0.02) for i in range(5)]
    for c in collectors:
        c.start()
    time.sleep(0.15)
    for c in collectors:
        c.stop()
    for c in collectors:
        c.join(timeout=1.0)
        assert not c.is_alive()

    for s in sources:
        assert s.update_count >= 3
    assert len(updates) > 0
