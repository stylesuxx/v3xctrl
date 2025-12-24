"""Shared telemetry context for accessing telemetry state across components."""
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional


@dataclass
class ServiceFlags:
    """Service status flags from telemetry."""
    video: bool = False
    debug: bool = False

    @classmethod
    def from_byte(cls, byte: int) -> 'ServiceFlags':
        """Parse service flags from byte value."""
        return cls(
            video=bool(byte & (1 << 0)),
            debug=bool(byte & (1 << 1))
        )


@dataclass
class GstFlags:
    """GStreamer status flags from telemetry."""
    recording: bool = False

    @classmethod
    def from_byte(cls, byte: int) -> 'GstFlags':
        """Parse GST flags from byte value."""
        return cls(
            recording=bool(byte & (1 << 0))
        )


@dataclass
class VideoCoreFlags:
    """VideoCore throttling flags from telemetry."""
    current: int = 0
    history: int = 0

    @classmethod
    def from_byte(cls, byte: int) -> 'VideoCoreFlags':
        """Parse VideoCore flags from byte value."""
        return cls(
            current=byte & 0x0F,
            history=(byte >> 4) & 0x0F
        )


@dataclass
class BatteryData:
    """Battery telemetry data."""
    icon: int = 0
    voltage: str = "0.00V"
    average_voltage: str = "0.00V"
    percent: str = "0%"
    warning: bool = False


@dataclass
class SignalData:
    """Signal telemetry data."""
    quality: Dict[str, int] = field(default_factory=lambda: {"rsrq": -1, "rsrp": -1})
    band: str = "BAND ?"
    cell: str = "CELL ?"


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
                      percent: str, warning: bool) -> None:
        """Update battery data."""
        with self._lock:
            self._battery = BatteryData(
                icon=icon,
                voltage=voltage,
                average_voltage=average_voltage,
                percent=percent,
                warning=warning
            )

    def get_services(self) -> ServiceFlags:
        """Get current service flags (thread-safe)."""
        with self._lock:
            return ServiceFlags(
                video=self._services.video,
                debug=self._services.debug
            )

    def get_gst(self) -> GstFlags:
        """Get current GST flags (thread-safe)."""
        with self._lock:
            return GstFlags(recording=self._gst.recording)

    def get_videocore(self) -> VideoCoreFlags:
        """Get current VideoCore flags (thread-safe)."""
        with self._lock:
            return VideoCoreFlags(
                current=self._videocore.current,
                history=self._videocore.history
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
