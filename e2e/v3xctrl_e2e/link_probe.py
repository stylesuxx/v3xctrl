"""Link quality measured with ping before the cases run.

A failed video check next to "relay path: 8% loss" reads differently from one
next to a clean link, so the run reports what the network looked like. The
probe runs on the idle link; a stream adds its own load on top.
"""

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

PING_INTERVAL_SECONDS = 0.2
# Grace for the last replies after the final request
PING_DEADLINE_MARGIN_SECONDS = 5

PACKETS_PATTERN = re.compile(r"(?P<sent>\d+) packets transmitted, (?P<received>\d+) (?:packets )?received")
RTT_PATTERN = re.compile(
    r"rtt min/avg/max/mdev = (?P<minimum>[\d.]+)/(?P<average>[\d.]+)/(?P<maximum>[\d.]+)/(?P<deviation>[\d.]+) ms"
)


@dataclass(frozen=True)
class LinkQuality:
    sent: int
    received: int
    rtt_average_ms: float | None = None
    rtt_maximum_ms: float | None = None
    jitter_ms: float | None = None

    @property
    def loss_percent(self) -> float:
        return 100.0 * (self.sent - self.received) / self.sent if self.sent > 0 else 100.0

    def describe(self) -> str:
        if self.received == 0:
            return f"no answer to {self.sent} pings"

        return (
            f"{self.loss_percent:.1f}% loss, rtt avg {self.rtt_average_ms:.0f} ms, "
            f"max {self.rtt_maximum_ms:.0f} ms, jitter {self.jitter_ms:.0f} ms"
        )


@dataclass(frozen=True)
class LinkReport:
    path: str
    host: str
    quality: LinkQuality | None

    def describe(self) -> str:
        measured = "probe failed" if self.quality is None else self.quality.describe()
        return f"{self.path} ({self.host}): {measured}"


def ping_command(host: str, seconds: float) -> list[str]:
    count = max(1, int(seconds / PING_INTERVAL_SECONDS))
    deadline = int(seconds) + PING_DEADLINE_MARGIN_SECONDS
    return ["ping", "-q", "-n", "-i", str(PING_INTERVAL_SECONDS), "-c", str(count), "-w", str(deadline), host]


def parse_ping_output(text: str) -> LinkQuality | None:
    packets = PACKETS_PATTERN.search(text)
    if packets is None:
        return None

    sent, received = int(packets["sent"]), int(packets["received"])
    rtt = RTT_PATTERN.search(text)
    if rtt is None:
        return LinkQuality(sent=sent, received=received)

    return LinkQuality(
        sent=sent,
        received=received,
        rtt_average_ms=float(rtt["average"]),
        rtt_maximum_ms=float(rtt["maximum"]),
        jitter_ms=float(rtt["deviation"]),
    )


def probe_from_here(
    host: str,
    seconds: float,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> LinkQuality | None:
    try:
        completed = runner(
            ping_command(host, seconds),
            capture_output=True,
            text=True,
            timeout=seconds + PING_DEADLINE_MARGIN_SECONDS * 2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    return parse_ping_output(completed.stdout)


def relay_address(relay_host: str) -> str:
    """The host part of the relay's host:port."""
    return relay_host.rsplit(":", 1)[0]
