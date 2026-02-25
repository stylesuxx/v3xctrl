import logging
import shutil
import subprocess
import threading
import time


def get_ntp_offset_chrony() -> int:
    """Returns offset in microseconds."""
    try:
        result = subprocess.run(
            ["chronyc", "-c", "tracking"],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0:
            raise RuntimeError(f"chronyc failed: {result.stderr.strip()}")

        fields = result.stdout.strip().split(",")
        if len(fields) < 5:
            raise RuntimeError(f"Unexpected chronyc output: {result.stdout.strip()}")

        offset_seconds = float(fields[4])
        return int(offset_seconds * 1_000_000)

    except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
        raise RuntimeError(f"Failed to get NTP offset from chronyc: {e}") from e


def get_ntp_offset_ntplib() -> int:
    """Returns offset in microseconds."""
    try:
        import ntplib
        client = ntplib.NTPClient()
        response = client.request("pool.ntp.org", version=3, timeout=5)
        return int(response.offset * 1_000_000)

    except Exception as e:
        raise RuntimeError(f"Failed to get NTP offset from ntplib: {e}") from e


class NTPClock:
    def __init__(self, poll_interval: float = 10.0) -> None:
        self._poll_interval = poll_interval

        if shutil.which("chronyc"):
            self._offset_fn = get_ntp_offset_chrony
            logging.info("NTP offset: using chronyc")
        else:
            self._offset_fn = get_ntp_offset_ntplib
            logging.info("NTP offset: using ntplib")

        self._offset_us: int = 0
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def get_time(self) -> tuple[int, int]:
        wall_time_us = int(time.time() * 1_000_000)

        return (wall_time_us, self._offset_us)

    def stop(self) -> None:
        self._stop_event.set()

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(timeout=self._poll_interval):
            try:
                self._offset_us = self._offset_fn()
            except RuntimeError:
                logging.warning("NTP offset: query failed, keeping last known offset")
