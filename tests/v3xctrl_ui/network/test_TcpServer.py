import socket
import threading
import time
import unittest

from v3xctrl_tcp.framing import recv_message, send_message
from v3xctrl_ui.network.TcpServer import TcpServer


def _free_port() -> int:
    """Get an available port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_tcp(port: int, timeout: float = 2.0) -> None:
    """Wait until a TCP server is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
            s.close()
            return
        except ConnectionRefusedError:
            time.sleep(0.05)
    raise TimeoutError(f"TCP server on port {port} did not start in time")


class TestTcpServerVideo(unittest.TestCase):
    """Test video channel: TCP inbound -> UDP to localhost:videoPort."""

    def setUp(self) -> None:
        self.video_port = _free_port()
        self.control_port = _free_port()
        self.server = TcpServer(self.video_port, self.control_port)
        self.server.start()
        _wait_for_tcp(self.video_port)

    def tearDown(self) -> None:
        self.server.stop()

    def test_video_forwarding(self) -> None:
        """TCP video data is forwarded as UDP to localhost:videoPort."""
        # Set up a UDP listener on videoPort to receive forwarded data
        udp_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_recv.bind(("127.0.0.1", self.video_port))
        udp_recv.settimeout(2.0)

        # Connect TCP client (simulating streamer)
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        tcp_client.connect(("127.0.0.1", self.video_port))

        try:
            # Send video frame over TCP
            payload = b"\x00\x01\x02" * 100
            self.assertTrue(send_message(tcp_client, payload))

            # Receive it on UDP
            data, addr = udp_recv.recvfrom(65535)
            self.assertEqual(data, payload)
            self.assertEqual(addr[0], "127.0.0.1")

        finally:
            tcp_client.close()
            udp_recv.close()

    def test_video_multiple_frames(self) -> None:
        """Multiple video frames are forwarded sequentially."""
        udp_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_recv.bind(("127.0.0.1", self.video_port))
        udp_recv.settimeout(2.0)

        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        tcp_client.connect(("127.0.0.1", self.video_port))

        try:
            frames = [b"frame1", b"frame2", b"frame3"]
            for frame in frames:
                self.assertTrue(send_message(tcp_client, frame))

            for frame in frames:
                data, _ = udp_recv.recvfrom(65535)
                self.assertEqual(data, frame)

        finally:
            tcp_client.close()
            udp_recv.close()

    def test_video_client_disconnect_and_reconnect(self) -> None:
        """After client disconnects, server accepts a new connection."""
        udp_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_recv.bind(("127.0.0.1", self.video_port))
        udp_recv.settimeout(2.0)

        # First connection
        tcp_client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client1.connect(("127.0.0.1", self.video_port))
        send_message(tcp_client1, b"first")
        data, _ = udp_recv.recvfrom(65535)
        self.assertEqual(data, b"first")
        tcp_client1.close()

        # Give server time to detect disconnect and re-enter accept
        time.sleep(0.2)

        # Second connection
        tcp_client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client2.connect(("127.0.0.1", self.video_port))
        send_message(tcp_client2, b"second")
        data, _ = udp_recv.recvfrom(65535)
        self.assertEqual(data, b"second")

        tcp_client2.close()
        udp_recv.close()


class TestTcpServerControl(unittest.TestCase):
    """Test control channel: bidirectional TCP <-> UDP."""

    def setUp(self) -> None:
        self.video_port = _free_port()
        self.control_port = _free_port()
        self.server = TcpServer(self.video_port, self.control_port)
        self.server.start()
        _wait_for_tcp(self.control_port)
        # Give server time to handle the probe connection and loop back
        # to accept (bidirectional channel has outbound thread to join).
        time.sleep(1.5)

    def tearDown(self) -> None:
        self.server.stop()

    def test_control_inbound(self) -> None:
        """TCP control data is forwarded as UDP to localhost:controlPort."""
        udp_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_recv.bind(("127.0.0.1", self.control_port))
        udp_recv.settimeout(2.0)

        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        tcp_client.connect(("127.0.0.1", self.control_port))

        try:
            payload = b"control_command"
            self.assertTrue(send_message(tcp_client, payload))

            data, addr = udp_recv.recvfrom(65535)
            self.assertEqual(data, payload)
            self.assertEqual(addr[0], "127.0.0.1")

        finally:
            tcp_client.close()
            udp_recv.close()

    def test_control_bidirectional(self) -> None:
        """UDP replies on ephemeral port are forwarded back over TCP."""
        # Set up UDP socket on controlPort to receive and reply
        udp_component = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_component.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_component.bind(("127.0.0.1", self.control_port))
        udp_component.settimeout(2.0)

        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        tcp_client.connect(("127.0.0.1", self.control_port))

        try:
            # Send command over TCP -> arrives as UDP
            send_message(tcp_client, b"command")
            data, source_addr = udp_component.recvfrom(65535)
            self.assertEqual(data, b"command")

            # Reply via UDP to the source (ephemeral port E2)
            udp_component.sendto(b"response", source_addr)

            # Should arrive back over TCP
            response = recv_message(tcp_client)
            self.assertEqual(response, b"response")

        finally:
            tcp_client.close()
            udp_component.close()

    def test_control_multiple_roundtrips(self) -> None:
        """Multiple command-response roundtrips work correctly."""
        udp_component = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_component.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_component.bind(("127.0.0.1", self.control_port))
        udp_component.settimeout(2.0)

        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        tcp_client.connect(("127.0.0.1", self.control_port))

        try:
            for i in range(5):
                cmd = f"cmd_{i}".encode()
                reply = f"reply_{i}".encode()

                send_message(tcp_client, cmd)
                data, source_addr = udp_component.recvfrom(65535)
                self.assertEqual(data, cmd)

                udp_component.sendto(reply, source_addr)
                response = recv_message(tcp_client)
                self.assertEqual(response, reply)

        finally:
            tcp_client.close()
            udp_component.close()


class TestTcpServerLifecycle(unittest.TestCase):
    """Test server start/stop lifecycle."""

    def test_clean_shutdown(self) -> None:
        """Server shuts down cleanly without hanging."""
        video_port = _free_port()
        control_port = _free_port()
        server = TcpServer(video_port, control_port)
        server.start()
        _wait_for_tcp(video_port)

        # Connect a client
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.connect(("127.0.0.1", video_port))

        # Stop should complete within timeout
        server.stop()
        tcp_client.close()

    def test_stop_without_connections(self) -> None:
        """Server stops cleanly when no clients ever connected."""
        video_port = _free_port()
        control_port = _free_port()
        server = TcpServer(video_port, control_port)
        server.start()
        _wait_for_tcp(video_port)
        server.stop()

    def test_stop_before_start(self) -> None:
        """Stopping a server that was never started does not crash."""
        server = TcpServer(_free_port(), _free_port())
        server.stop()


if __name__ == "__main__":
    unittest.main()
