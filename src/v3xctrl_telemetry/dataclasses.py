"""Telemetry dataclasses with serialization support."""
from dataclasses import dataclass


@dataclass
class GstFlags:
    """GStreamer status flags for telemetry."""
    recording: bool = False
    udp_overrun: bool = False

    def to_byte(self) -> int:
        """Pack flags into a single byte."""
        byte = 0
        if self.recording:
            byte |= (1 << 0)
        if self.udp_overrun:
            byte |= (1 << 1)
        return byte

    @classmethod
    def from_byte(cls, byte: int) -> 'GstFlags':
        """Parse flags from byte value."""
        return cls(
            recording=bool(byte & (1 << 0)),
            udp_overrun=bool(byte & (1 << 1))
        )


@dataclass
class ServiceFlags:
    """Service status flags for telemetry."""
    video: bool = False
    reverse_shell: bool = False
    debug: bool = False

    def to_byte(self) -> int:
        """Pack flags into a single byte."""
        byte = 0
        if self.video:
            byte |= (1 << 0)
        if self.reverse_shell:
            byte |= (1 << 1)
        if self.debug:
            byte |= (1 << 2)
        return byte

    @classmethod
    def from_byte(cls, byte: int) -> 'ServiceFlags':
        """Parse flags from byte value."""
        return cls(
            video=bool(byte & (1 << 0)),
            reverse_shell=bool(byte & (1 << 1)),
            debug=bool(byte & (1 << 2))
        )


@dataclass
class ThrottleFlags:
    """Individual throttle condition flags."""
    undervolt: bool = False
    freq_capped: bool = False
    throttled: bool = False
    soft_temp_limit: bool = False

    def to_nibble(self) -> int:
        """Pack flags into a 4-bit nibble."""
        nibble = 0
        if self.undervolt:
            nibble |= (1 << 0)
        if self.freq_capped:
            nibble |= (1 << 1)
        if self.throttled:
            nibble |= (1 << 2)
        if self.soft_temp_limit:
            nibble |= (1 << 3)
        return nibble

    @classmethod
    def from_nibble(cls, nibble: int) -> 'ThrottleFlags':
        """Parse flags from 4-bit nibble."""
        return cls(
            undervolt=bool(nibble & (1 << 0)),
            freq_capped=bool(nibble & (1 << 1)),
            throttled=bool(nibble & (1 << 2)),
            soft_temp_limit=bool(nibble & (1 << 3))
        )


@dataclass
class VideoCoreFlags:
    """VideoCore throttling flags for telemetry."""
    current: ThrottleFlags = None
    history: ThrottleFlags = None

    def __post_init__(self):
        if self.current is None:
            self.current = ThrottleFlags()
        if self.history is None:
            self.history = ThrottleFlags()

    def to_byte(self) -> int:
        """Pack flags into a single byte (lower nibble=current, upper=history)."""
        return (self.current.to_nibble() & 0x0F) | ((self.history.to_nibble() & 0x0F) << 4)

    @classmethod
    def from_byte(cls, byte: int) -> 'VideoCoreFlags':
        """Parse flags from byte value."""
        return cls(
            current=ThrottleFlags.from_nibble(byte & 0x0F),
            history=ThrottleFlags.from_nibble((byte >> 4) & 0x0F)
        )


# Telemetry payload dataclasses

@dataclass
class SignalInfo:
    """Signal quality information."""
    rsrq: int = -1
    rsrp: int = -1


@dataclass
class CellInfo:
    """Cell tower information."""
    id: str = '?'
    band: str = '?'


@dataclass
class LocationInfo:
    """GPS location information."""
    lat: float = 0.0
    lng: float = 0.0


@dataclass
class BatteryInfo:
    """Battery telemetry information."""
    vol: int = 0
    avg: int = 0
    pct: int = 0
    wrn: bool = False


@dataclass
class TelemetryPayload:
    """Complete telemetry payload."""
    sig: SignalInfo
    cell: CellInfo
    loc: LocationInfo
    bat: BatteryInfo
    svc: int = 0
    vc: int = 0
    gst: int = 0
