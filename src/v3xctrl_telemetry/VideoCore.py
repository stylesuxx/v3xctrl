from dataclasses import dataclass
import subprocess
from typing import Dict


@dataclass
class Flags:
    undervolt: bool = False
    freq_capped: bool = False
    throttled: bool = False
    soft_temp_limit: bool = False


class VideoCoreTelemetry:
    def __init__(self):
        self.current = Flags()
        self.history = Flags()

    def update(self) -> None:
        """
        Update current and historical flags from vcgencmd.
        """
        # Example: throttled=0x50005
        out = self._run_vcgencmd("get_throttled")

        try:
            value = int(out.split("=", 1)[1], 16)
        except Exception:
            raise RuntimeError(f"Unexpected vcgencmd output: {out}")

        # Current flags (bits 0–3)
        self.current.undervolt = bool(value & (1 << 0))
        self.current.freq_capped = bool(value & (1 << 1))
        self.current.throttled = bool(value & (1 << 2))
        self.current.soft_temp_limit = bool(value & (1 << 3))

        # Historical flags (bits 16–19)
        self.history.undervolt = bool(value & (1 << 16))
        self.history.freq_capped = bool(value & (1 << 17))
        self.history.throttled = bool(value & (1 << 18))
        self.history.soft_temp_limit = bool(value & (1 << 19))

    def get_byte(self) -> int:
        # TODO: Building the flags should be done somewhere else
        """
        Return an 8-bit integer:
        lower nibble  = current flags
        upper nibble  = historical flags
        """
        b = 0

        b |= int(self.current.undervolt) << 0
        b |= int(self.current.freq_capped) << 1
        b |= int(self.current.throttled) << 2
        b |= int(self.current.soft_temp_limit) << 3

        b |= int(self.history.undervolt) << 4
        b |= int(self.history.freq_capped) << 5
        b |= int(self.history.throttled) << 6
        b |= int(self.history.soft_temp_limit) << 7

        return b & 0xFF

    def get_current(self) -> Flags:
        return self.current

    def get_history(self) -> Flags:
        return self.history

    def state(self) -> Dict[str, Flags]:
        return {
            'current': self.current,
            'history': self.history,
        }

    def _run_vcgencmd(self, *args: str) -> str:
        out = subprocess.check_output(
            ["vcgencmd", *args],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=1.0,
        )

        return out.strip()
