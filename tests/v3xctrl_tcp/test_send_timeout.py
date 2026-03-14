import socket
import struct

from v3xctrl_tcp.send_timeout import configure_send_timeout


class TestConfigureSendTimeout:
    """Verify that configure_send_timeout sets SO_SNDTIMEO correctly."""

    def _get_sndtimeo_ms(self, sock: socket.socket) -> int:
        raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 16)
        sec, usec = struct.unpack("ll", raw)
        return sec * 1000 + usec // 1000

    def test_sets_timeout(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            configure_send_timeout(sock, 200)
            # Kernel may round slightly, allow ±5ms
            assert abs(self._get_sndtimeo_ms(sock) - 200) <= 5
        finally:
            sock.close()

    def test_sets_short_timeout(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            configure_send_timeout(sock, 50)
            assert abs(self._get_sndtimeo_ms(sock) - 50) <= 5
        finally:
            sock.close()
