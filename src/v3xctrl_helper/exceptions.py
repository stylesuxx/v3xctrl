from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from v3xctrl_control.message import PeerInfo


class UnauthorizedError(Exception):
    pass


class PeerRegistrationAborted(Exception):
    """Raised when peer registration is aborted intentionally."""

    pass


class PeerRegistrationError(Exception):
    def __init__(self, failures: dict[str, Exception], successes: dict[str, PeerInfo]):
        self.failures = failures
        self.successes = successes
        failed_ports = list(failures.keys())
        super().__init__(f"Registration failed for ports: {failed_ports}")
