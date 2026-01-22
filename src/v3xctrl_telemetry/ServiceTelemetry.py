import subprocess

from v3xctrl_telemetry.dataclasses import ServiceFlags


class ServiceTelemetry:
    # Service name mapping: field name -> systemd service name
    SERVICE_NAMES = {
        'video': 'v3xctrl-video.service',
        'reverse_shell': 'v3xctrl-reverse-shell.service',
        'debug': 'v3xctrl-debug.service',
    }

    def __init__(self):
        self._state = ServiceFlags()

    def _is_active(self, service: str) -> bool:
        return subprocess.call(
            ["systemctl", "is-active", "--quiet", service],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0

    def update(self) -> None:
        for field_name, service_name in self.SERVICE_NAMES.items():
            setattr(self._state, field_name, self._is_active(service_name))

    def get_state(self) -> ServiceFlags:
        return self._state

    def get_byte(self) -> int:
        """Return flags packed as a byte for telemetry transmission."""
        return self._state.to_byte()
