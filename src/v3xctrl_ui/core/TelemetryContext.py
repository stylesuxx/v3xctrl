"""Shared telemetry context for accessing telemetry state across components."""
from threading import Lock

from v3xctrl_ui.core.dataclasses import (
    ServiceFlags,
    GstFlags,
    VideoCoreFlags,
    ThrottleFlags,
    BatteryData,
    SignalData,
)


class TelemetryContext:
    """
    Thread-safe context for sharing telemetry state across components.

    This provides a centralized place for telemetry data that can be
    accessed by both the OSD (which updates it) and the Menu/StreamerTab
    (which reads it).
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._services = ServiceFlags()
        self._gst = GstFlags()
        self._videocore = VideoCoreFlags()
        self._battery = BatteryData()
        self._signal = SignalData()

    def update_services(self, byte_value: int) -> None:
        """Update service flags from telemetry byte."""
        with self._lock:
            self._services = ServiceFlags.from_byte(byte_value)

    def update_gst(self, byte_value: int) -> None:
        """Update GST flags from telemetry byte."""
        with self._lock:
            self._gst = GstFlags.from_byte(byte_value)

    def update_videocore(self, byte_value: int) -> None:
        """Update VideoCore flags from telemetry byte."""
        with self._lock:
            self._videocore = VideoCoreFlags.from_byte(byte_value)

    def update_signal_quality(self, rsrq: int, rsrp: int) -> None:
        """Update signal quality values."""
        with self._lock:
            self._signal.quality = {"rsrq": rsrq, "rsrp": rsrp}

    def update_signal_band(self, band: str) -> None:
        """Update signal band."""
        with self._lock:
            self._signal.band = band

    def update_signal_cell(self, cell: str) -> None:
        """Update signal cell."""
        with self._lock:
            self._signal.cell = cell

    def update_battery(self, icon: int, voltage: str, average_voltage: str,
                      percent: str, current: str, warning: bool) -> None:
        """Update battery data."""
        with self._lock:
            self._battery = BatteryData(
                icon=icon,
                voltage=voltage,
                average_voltage=average_voltage,
                percent=percent,
                current=current,
                warning=warning
            )

    def get_services(self) -> ServiceFlags:
        """Get current service flags (thread-safe)."""
        with self._lock:
            return ServiceFlags(
                video=self._services.video,
                reverse_shell=self._services.reverse_shell,
                debug=self._services.debug
            )

    def get_gst(self) -> GstFlags:
        """Get current GST flags (thread-safe)."""
        with self._lock:
            return GstFlags(
                recording=self._gst.recording,
                udp_overrun=self._gst.udp_overrun
            )

    def get_videocore(self) -> VideoCoreFlags:
        """Get current VideoCore flags (thread-safe)."""
        with self._lock:
            return VideoCoreFlags(
                current=ThrottleFlags(
                    undervolt=self._videocore.current.undervolt,
                    freq_capped=self._videocore.current.freq_capped,
                    throttled=self._videocore.current.throttled,
                    soft_temp_limit=self._videocore.current.soft_temp_limit
                ),
                history=ThrottleFlags(
                    undervolt=self._videocore.history.undervolt,
                    freq_capped=self._videocore.history.freq_capped,
                    throttled=self._videocore.history.throttled,
                    soft_temp_limit=self._videocore.history.soft_temp_limit
                )
            )

    def get_signal(self) -> SignalData:
        """Get current signal data (thread-safe)."""
        with self._lock:
            return SignalData(
                quality=self._signal.quality.copy(),
                band=self._signal.band,
                cell=self._signal.cell
            )

    def get_battery(self) -> BatteryData:
        """Get current battery data (thread-safe)."""
        with self._lock:
            return BatteryData(
                icon=self._battery.icon,
                voltage=self._battery.voltage,
                average_voltage=self._battery.average_voltage,
                percent=self._battery.percent,
                current=self._battery.current,
                warning=self._battery.warning
            )

    def reset(self) -> None:
        """Reset all telemetry data to defaults."""
        with self._lock:
            self._services = ServiceFlags()
            self._gst = GstFlags()
            self._videocore = VideoCoreFlags()
            self._battery = BatteryData()
            self._signal = SignalData()
