from typing import Dict

from v3xctrl_control.message import PeerInfo


class UnauthorizedError(Exception):
    pass


class PeerRegistrationAborted(Exception):
    """Raised when peer registration is aborted intentionally."""
    pass


class PeerRegistrationError(Exception):
    def __init__(self, failures: Dict[str, Exception], successes: Dict[str, PeerInfo]):
        self.failures = failures
        self.successes = successes
        failed_ports = list(failures.keys())
        super().__init__(f"Registration failed for ports: {failed_ports}")
