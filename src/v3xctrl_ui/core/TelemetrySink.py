"""Ingestion of control channel telemetry into the shared telemetry context."""

import time
from dataclasses import dataclass

from v3xctrl_control.message import Latency, Message, Telemetry
from v3xctrl_helper import SlidingWindowAverage
from v3xctrl_ui.core.StatusLevel import StatusLevel
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.core.TelemetryParser import parse_telemetry

GOOD_LATENCY_MILLISECONDS = 40
WARNING_LATENCY_MILLISECONDS = 75


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
    """

    def __init__(self, telemetry_context: TelemetryContext) -> None:
        self.telemetry_context = telemetry_context

        self._is_spectator = False
        self._latency = LatencyReading()
        self._latency_samples = SlidingWindowAverage(window_seconds=1.0)

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
