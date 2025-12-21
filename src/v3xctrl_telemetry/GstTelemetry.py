from dataclasses import dataclass

from v3xctrl_gst.ControlClient import ControlClient


@dataclass
class Stats:
    recording: bool = False


class GstTelemetry:
    def __init__(self, socket_path: str = '/tmp/v3xctrl.sock'):
        self._stats = Stats()
        self._client = ControlClient(socket_path=socket_path)

    def update(self) -> None:
        try:
            response = self._client.stats()
            if response.get('status') == 'success':
                # Update stats from response
                self._stats.recording = response.get('recording', False)
        except Exception:
            # If we can't reach the control socket, assume not recording
            self._stats.recording = False

    def get_state(self) -> Stats:
        return self._stats
