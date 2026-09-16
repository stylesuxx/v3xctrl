"""Ingestion of control channel telemetry into the shared telemetry context."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from v3xctrl_control.message import Latency, Message, Telemetry
from v3xctrl_helper import SlidingWindowAverage
from v3xctrl_ui.core.StatusLevel import StatusLevel
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.core.TelemetryParser import parse_telemetry

logger = logging.getLogger(__name__)

GOOD_LATENCY_MILLISECONDS = 40
WARNING_LATENCY_MILLISECONDS = 75
TELEMETRY_REPORT_INTERVAL_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class LatencyReading:
    """The one way latency estimate.

    `milliseconds` is the rolling average over the sample window. It is None
    until the first measurement arrives and while spectating, which
    `is_measurable` tells apart.
    """

    milliseconds: int | None = None
    level: StatusLevel = StatusLevel.NEUTRAL
    is_measurable: bool = True


class TelemetrySink:
    """Turns control channel messages into shared telemetry state.

    The only things it writes are the `TelemetryContext` it is given and its
    own latency reading, so ingestion can be exercised without a display.

    Messages arrive on the receive thread while the reading is read on the main
    thread. Each reading is a new frozen value bound to one attribute, so a
    reader sees either the old one or the new one.

    The first telemetry message of a connection and the message count per
    report interval are logged, which is what an unattended run has to go on.
    """

    def __init__(
        self,
        telemetry_context: TelemetryContext,
        report_interval_seconds: float = TELEMETRY_REPORT_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.telemetry_context = telemetry_context
        self._report_interval_seconds = report_interval_seconds
        self._clock = clock

        self._is_spectator = False
        self._latency = LatencyReading()
        self._latency_samples = SlidingWindowAverage(window_seconds=1.0)

        self._has_received_telemetry = False
        self._telemetry_count = 0
        self._report_window_started: float | None = None

    @property
    def latency(self) -> LatencyReading:
        return self._latency

    def set_spectator_mode(self, is_spectator: bool) -> None:
        self._is_spectator = is_spectator

    def handle_message(self, message: Message) -> None:
        match message:
            case Telemetry():
                self._handle_telemetry(message)

            case Latency():
                self._handle_latency(message)

    def reset(self) -> None:
        self.telemetry_context.reset()
        self._latency_samples.clear()
        self._latency = LatencyReading()

        self._has_received_telemetry = False
        self._telemetry_count = 0
        self._report_window_started = None

    def _record_telemetry_arrival(self) -> None:
        if not self._has_received_telemetry:
            self._has_received_telemetry = True
            logger.info("First telemetry message received")

        now = self._clock()
        if self._report_window_started is None:
            self._report_window_started = now

        self._telemetry_count += 1

        elapsed = now - self._report_window_started
        if elapsed >= self._report_interval_seconds:
            logger.info(f"Telemetry: {self._telemetry_count} messages in last {round(elapsed)}s")
            self._telemetry_count = 0
            self._report_window_started = now

    def _handle_latency(self, message: Latency) -> None:
        # Latency is measured against the streamer, so a spectator has nothing
        # to measure
        if self._is_spectator:
            self._latency = LatencyReading(is_measurable=False)

            return

        # RTT/2 for one-way network latency estimate
        milliseconds = (time.time() - message.timestamp) * 1000 / 2
        self._latency_samples.append(milliseconds)

        average = round(self._latency_samples.average)

        if average <= GOOD_LATENCY_MILLISECONDS:
            level = StatusLevel.GOOD
        elif average <= WARNING_LATENCY_MILLISECONDS:
            level = StatusLevel.WARNING
        else:
            level = StatusLevel.BAD

        self._latency = LatencyReading(milliseconds=average, level=level)

    def _handle_telemetry(self, message: Telemetry) -> None:
        self._record_telemetry_arrival()

        data = parse_telemetry(message)
        values = message.get_values()

        self.telemetry_context.update_signal_quality(values["sig"]["rsrq"], values["sig"]["rsrp"])
        self.telemetry_context.update_signal_band(data.signal_band)
        self.telemetry_context.update_signal_cell(data.signal_cell)

        self.telemetry_context.update_battery(
            icon=data.battery_icon,
            voltage=data.battery_voltage,
            average_voltage=data.battery_average_voltage,
            percent=data.battery_percent,
            current=data.battery_current,
            warning=data.battery_warning,
        )

        self.telemetry_context.update_gps(
            fix_type=data.gps_fix_type,
            speed=data.gps_speed,
            satellites=data.gps_satellites,
        )
        self.telemetry_context.update_services(values.get("svc", 0))
        self.telemetry_context.update_gst(values.get("gst", 0))
        self.telemetry_context.update_videocore(values.get("vc", 0))
