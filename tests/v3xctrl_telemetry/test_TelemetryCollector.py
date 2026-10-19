"""Tests for TelemetryCollector.

Lifecycle behaviour (construction, retry backoff, rebuild, unavailable state, logging) is
driven through `run_once()` with an explicit clock, so no test sleeps. The thread tests at
the bottom cover only the driver around that loop body.
"""

import logging
import threading
import time
from typing import Any

import pytest

from v3xctrl_telemetry.TelemetryCollector import TelemetryCollector

COLLECTOR_LOGGER = "v3xctrl_telemetry.TelemetryCollector"
UNAVAILABLE = "unavailable"


class FlakySource:
    """Source whose update() raises while `is_failing` is set."""

    def __init__(self, state: Any = "ok") -> None:
        self.update_count = 0
        self.is_failing = False
        self._state = state

    def update(self) -> None:
        self.update_count += 1
        if self.is_failing:
            raise RuntimeError("source failed")

    def get_state(self) -> Any:
        return self._state


class CountingFactory:
    """Factory that raises for its first `failures` calls, then returns `source`."""

    def __init__(self, source: Any = None, failures: int = 0) -> None:
        self.call_count = 0
        self.source = source if source is not None else FlakySource()
        self._failures = failures

    def __call__(self) -> Any:
        self.call_count += 1
        if self.call_count <= self._failures:
            raise RuntimeError("device absent")

        return self.source


def _make_collector(factory: Any, *, interval: float = 1.0) -> tuple[TelemetryCollector, list[Any]]:
    updates: list[Any] = []
    collector = TelemetryCollector("dev", factory, UNAVAILABLE, updates.append, interval)

    return collector, updates


def test_source_is_constructed_on_the_first_tick() -> None:
    factory = CountingFactory(FlakySource("snapshot"))
    collector, updates = _make_collector(factory)

    deadline = collector.run_once(100.0)

    assert factory.call_count == 1
    assert updates == ["snapshot"]
    assert deadline == 101.0


def test_deadline_is_measured_from_the_start_of_the_tick() -> None:
    """The next deadline does not include the time the tick itself took."""
    collector, _ = _make_collector(CountingFactory(), interval=0.5)

    assert collector.run_once(100.0) == 100.5
    assert collector.run_once(100.5) == 101.0


def test_construction_failure_is_retried_on_a_backoff() -> None:
    factory = CountingFactory(FlakySource(), failures=2)
    collector, updates = _make_collector(factory)

    assert collector.run_once(100.0) == 101.0
    assert factory.call_count == 1

    # Before the retry deadline nothing is attempted
    assert collector.run_once(100.5) == 101.0
    assert factory.call_count == 1

    # Second attempt fails too, and the wait doubles
    assert collector.run_once(101.0) == 103.0
    assert factory.call_count == 2

    # Third attempt succeeds and the source is polled
    assert collector.run_once(103.0) == 104.0
    assert factory.call_count == 3
    assert updates == ["ok"]


def test_backoff_stops_growing_at_the_cap() -> None:
    collector, _ = _make_collector(CountingFactory(failures=10), interval=10.0)

    now = 100.0
    waits = []
    for _ in range(5):
        deadline = collector.run_once(now)
        waits.append(deadline - now)
        now = deadline

    assert waits == [10.0, 20.0, 30.0, 30.0, 30.0]
    assert TelemetryCollector.MAX_RETRY_INTERVAL_S == 30.0


def test_startup_failure_leaves_the_store_untouched() -> None:
    """The store already holds defaults, so there is nothing to write."""
    collector, updates = _make_collector(CountingFactory(failures=3))

    now = 100.0
    for _ in range(3):
        now = collector.run_once(now)

    assert updates == []


def test_source_is_rebuilt_after_consecutive_update_failures() -> None:
    source = FlakySource()
    factory = CountingFactory(source)
    collector, updates = _make_collector(factory)

    collector.run_once(100.0)
    source.is_failing = True

    assert collector.run_once(101.0) == 102.0
    assert collector.run_once(102.0) == 103.0
    assert factory.call_count == 1

    # Third failure in a row discards the source and schedules a rebuild
    assert collector.run_once(103.0) == 104.0
    assert updates == ["ok", UNAVAILABLE]

    collector.run_once(104.0)
    assert factory.call_count == 2


def test_transient_update_failures_keep_the_source() -> None:
    source = FlakySource()
    factory = CountingFactory(source)
    collector, updates = _make_collector(factory)

    collector.run_once(100.0)

    source.is_failing = True
    collector.run_once(101.0)
    collector.run_once(102.0)

    source.is_failing = False
    collector.run_once(103.0)

    assert factory.call_count == 1
    assert updates == ["ok", "ok"]
    assert TelemetryCollector.REBUILD_AFTER_FAILURES == 3


def test_unavailable_state_is_not_rewritten_on_every_tick() -> None:
    source = FlakySource()
    collector, updates = _make_collector(CountingFactory(source))

    collector.run_once(100.0)
    source.is_failing = True
    for now in (101.0, 102.0, 103.0):
        collector.run_once(now)

    assert updates == ["ok", UNAVAILABLE]

    # Ticks before the retry deadline do nothing at all
    for now in (103.2, 103.5, 103.9):
        assert collector.run_once(now) == 104.0

    assert updates == ["ok", UNAVAILABLE]


def test_fresh_state_flows_again_after_a_rebuild() -> None:
    source = FlakySource()
    factory = CountingFactory(source)
    collector, updates = _make_collector(factory)

    collector.run_once(100.0)
    source.is_failing = True
    for now in (101.0, 102.0, 103.0):
        collector.run_once(now)

    source.is_failing = False
    collector.run_once(104.0)

    assert factory.call_count == 2
    assert updates == ["ok", UNAVAILABLE, "ok"]


def test_get_state_failure_is_treated_as_an_update_failure() -> None:
    class BadStateSource:
        def update(self) -> None:
            return None

        def get_state(self) -> Any:
            raise RuntimeError("state read failed")

    collector, updates = _make_collector(CountingFactory(BadStateSource()))

    now = 100.0
    for _ in range(3):
        now = collector.run_once(now)

    assert updates == [UNAVAILABLE]


def test_unavailable_source_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    collector, _ = _make_collector(CountingFactory(failures=10))

    with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
        now = 100.0
        for _ in range(5):
            now = collector.run_once(now)

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "unavailable" in warnings[0].getMessage()


def test_failing_source_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    source = FlakySource()
    collector, _ = _make_collector(CountingFactory(source))
    collector.run_once(100.0)
    source.is_failing = True

    with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
        now = 101.0
        for _ in range(8):
            now = collector.run_once(now)

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "failing" in warnings[0].getMessage()


def test_recovery_is_logged_once_the_source_returns(caplog: pytest.LogCaptureFixture) -> None:
    collector, _ = _make_collector(CountingFactory(failures=1))

    with caplog.at_level(logging.INFO, logger=COLLECTOR_LOGGER):
        deadline = collector.run_once(100.0)
        collector.run_once(deadline)

    messages = [record.getMessage() for record in caplog.records]
    assert any("unavailable" in message for message in messages)
    assert any("recovered" in message for message in messages)


def test_healthy_collector_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    collector, _ = _make_collector(CountingFactory())

    with caplog.at_level(logging.DEBUG, logger=COLLECTOR_LOGGER):
        now = 100.0
        for _ in range(5):
            now = collector.run_once(now)

    assert [record for record in caplog.records if record.name == COLLECTOR_LOGGER] == []


def _drain_collector(collector: TelemetryCollector, *, runtime_s: float = 0.15) -> None:
    collector.start()
    time.sleep(runtime_s)
    collector.stop()
    collector.join(timeout=1.0)
    assert not collector.is_alive()


def test_thread_polls_until_stopped() -> None:
    source = FlakySource("snapshot")
    collector, updates = _make_collector(CountingFactory(source), interval=0.02)

    _drain_collector(collector)

    assert source.update_count >= 3
    assert updates and all(state == "snapshot" for state in updates)


def test_thread_survives_store_updater_exceptions() -> None:
    call_count = 0

    def bad_updater(state: Any) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("store updater failed")

    collector = TelemetryCollector("bad-updater", CountingFactory(), UNAVAILABLE, bad_updater, 0.02)
    _drain_collector(collector)

    assert call_count >= 3


def test_stop_returns_quickly_even_with_a_long_interval() -> None:
    collector, _ = _make_collector(CountingFactory(), interval=10.0)

    collector.start()
    time.sleep(0.05)
    started_at = time.monotonic()
    collector.stop()
    collector.join(timeout=1.0)
    elapsed = time.monotonic() - started_at

    assert not collector.is_alive()
    assert elapsed < 0.5, f"stop did not return promptly (elapsed={elapsed:.3f}s)"


def test_collector_is_a_daemon_thread_named_after_its_source() -> None:
    collector = TelemetryCollector("battery", CountingFactory(), UNAVAILABLE, lambda _state: None, 1.0)

    assert collector.daemon is True
    assert "battery" in collector.name


def test_stop_is_idempotent() -> None:
    collector, _ = _make_collector(CountingFactory(), interval=0.05)

    collector.start()
    time.sleep(0.05)
    collector.stop()
    collector.stop()
    collector.join(timeout=1.0)

    assert not collector.is_alive()


def test_stop_before_start_does_not_block() -> None:
    collector, _ = _make_collector(CountingFactory())

    collector.stop()

    assert not collector.is_alive()


def test_no_updates_after_stop() -> None:
    source = FlakySource()
    collector, _ = _make_collector(CountingFactory(source), interval=0.02)

    _drain_collector(collector, runtime_s=0.1)
    final_count = source.update_count
    time.sleep(0.1)

    assert source.update_count == final_count


def test_concurrent_collectors_do_not_deadlock() -> None:
    sources = [FlakySource(state=index) for index in range(5)]
    lock = threading.Lock()
    updates: list[Any] = []

    def make_updater() -> Any:
        def updater(state: Any) -> None:
            with lock:
                updates.append(state)

        return updater

    collectors = [
        TelemetryCollector(f"source-{index}", CountingFactory(sources[index]), UNAVAILABLE, make_updater(), 0.02)
        for index in range(5)
    ]
    for collector in collectors:
        collector.start()
    time.sleep(0.15)
    for collector in collectors:
        collector.stop()
    for collector in collectors:
        collector.join(timeout=1.0)
        assert not collector.is_alive()

    for source in sources:
        assert source.update_count >= 3
    assert len(updates) > 0
