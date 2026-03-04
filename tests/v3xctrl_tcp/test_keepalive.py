import socket

from v3xctrl_tcp.keepalive import configure_keepalive


class TestConfigureKeepalive:
    """Verify that configure_keepalive sets the expected socket options."""

    def test_enables_keepalive(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            configure_keepalive(sock)

            assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE) == 10
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL) == 5
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT) == 3
        finally:
            sock.close()
