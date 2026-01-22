import subprocess

from v3xctrl_telemetry.dataclasses import VideoCoreFlags


class VideoCoreTelemetry:
    def __init__(self):
        self._state = VideoCoreFlags()

    def update(self) -> None:
        """Update current and historical flags from vcgencmd."""
        # Example: throttled=0x50005
        out = self._run_vcgencmd("get_throttled")

        try:
            value = int(out.split("=", 1)[1], 16)
        except (ValueError, IndexError):
            raise RuntimeError(f"Unexpected vcgencmd output: {out}")

        # Current flags (bits 0–3)
        self._state.current.undervolt = bool(value & (1 << 0))
        self._state.current.freq_capped = bool(value & (1 << 1))
        self._state.current.throttled = bool(value & (1 << 2))
        self._state.current.soft_temp_limit = bool(value & (1 << 3))

        # Historical flags (bits 16–19)
        self._state.history.undervolt = bool(value & (1 << 16))
        self._state.history.freq_capped = bool(value & (1 << 17))
        self._state.history.throttled = bool(value & (1 << 18))
        self._state.history.soft_temp_limit = bool(value & (1 << 19))

    def get_state(self) -> VideoCoreFlags:
        return self._state

    def get_byte(self) -> int:
        """Return flags packed as a byte for telemetry transmission."""
        return self._state.to_byte()

    def _run_vcgencmd(self, *args: str) -> str:
        out = subprocess.check_output(
            ["vcgencmd", *args],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=1.0,
        )

        return out.strip()
