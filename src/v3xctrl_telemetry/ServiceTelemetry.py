from dataclasses import dataclass, fields
import subprocess


@dataclass
class Services:
    v3xctrl_video: bool = False
    v3xctrl_debug: bool = False


class ServiceTelemetry:
    def __init__(self):
        self.services = Services()

    def _is_active(self, service: str) -> bool:
        return subprocess.call(
            ["systemctl", "is-active", "--quiet", service],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0

    def update(self) -> None:
        for f in fields(self.services):
            service_name = f.name.replace("_", "-") + ".service"
            setattr(
                self.services,
                f.name,
                self._is_active(service_name),
            )

    def get_state(self) -> Services:
        return self.services

    def get_byte(self) -> int:
        """
        Pack service states into a single byte.
        Each service corresponds to a bit in field order:
        - bit 0: v3xctrl_video
        - bit 1: v3xctrl_debug
        """
        byte = 0
        for i, field in enumerate(fields(self.services)):
            if getattr(self.services, field.name):
                byte |= (1 << i)
        return byte & 0xFF
