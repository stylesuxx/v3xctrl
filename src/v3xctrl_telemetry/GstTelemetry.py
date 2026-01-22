from v3xctrl_gst.ControlClient import ControlClient
from v3xctrl_telemetry.dataclasses import GstFlags


class GstTelemetry:
    def __init__(self, socket_path: str = '/tmp/v3xctrl.sock'):
        self._state = GstFlags()
        self._client = ControlClient(socket_path=socket_path)

    def update(self) -> None:
        try:
            response = self._client.stats()
            self._state.recording = response.get('recording', False)
            self._state.udp_overrun = response.get('udp_overrun', False)
        except Exception:
            # Leave previous state
            pass

    def get_state(self) -> GstFlags:
        return self._state

    def get_byte(self) -> int:
        """Return flags packed as a byte for telemetry transmission."""
        return self._state.to_byte()
