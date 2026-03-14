import socket
import time
import unittest

from v3xctrl_tcp.framing import recv_message, send_message
from v3xctrl_tcp.TcpTunnel import TcpTunnel


def _free_port() -> int:
    """Get an available port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TcpServerHelper:
    """Simple TCP server for testing TcpTunnel connections."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", port))
        self.server_sock.listen(1)
        self.server_sock.settimeout(5.0)
        self.client_sock: socket.socket | None = None

    def accept(self) -> socket.socket:
        self.client_sock, _ = self.server_sock.accept()
        self.client_sock.setsockopt(
            socket.IPPROTO_TCP, socket.TCP_NODELAY, 1
        )
        return self.client_sock

    def close(self) -> None:
        if self.client_sock:
            self.client_sock.close()
        self.server_sock.close()


class TestTcpTunnelOutbound(unittest.TestCase):
    """Test outbound: local UDP component -> TcpTunnel -> TCP remote."""

    def setUp(self) -> None:
        self.tcp_port = _free_port()
        self.local_port = _free_port()
        self.server = _TcpServerHelper(self.tcp_port)

        self.tunnel = TcpTunnel(
            remote_host="127.0.0.1",
            remote_port=self.tcp_port,
            local_component_port=self.local_port,
            bidirectional=False,
        )
        self.tunnel.start()
        self.tunnel.wait_for_port(timeout=2.0)

        # Accept the tunnel's TCP connection
        self.tcp_client = self.server.accept()

    def tearDown(self) -> None:
        self.tunnel.stop()
        self.server.close()

    def test_outbound_forwarding(self) -> None:
        """UDP data sent to ephemeral port arrives over TCP."""
        udp_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            payload = b"hello from udp"
            udp_sender.sendto(
                payload, ("127.0.0.1", self.tunnel.ephemeral_port)
            )

            self.tcp_client.settimeout(2.0)
            data = recv_message(self.tcp_client)
            self.assertEqual(data, payload)
        finally:
            udp_sender.close()

    def test_outbound_multiple_packets(self) -> None:
        """Multiple UDP packets are forwarded sequentially over TCP."""
        udp_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            packets = [b"pkt1", b"pkt2", b"pkt3"]
            for pkt in packets:
                udp_sender.sendto(
                    pkt, ("127.0.0.1", self.tunnel.ephemeral_port)
                )

            self.tcp_client.settimeout(2.0)
            for pkt in packets:
                data = recv_message(self.tcp_client)
                self.assertEqual(data, pkt)
        finally:
            udp_sender.close()

    def test_outbound_large_packet(self) -> None:
        """Large UDP packet is forwarded over TCP."""
        udp_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            payload = b"\xab" * 1400  # typical video packet size
            udp_sender.sendto(
                payload, ("127.0.0.1", self.tunnel.ephemeral_port)
            )

            self.tcp_client.settimeout(2.0)
            data = recv_message(self.tcp_client)
            self.assertEqual(data, payload)
        finally:
            udp_sender.close()


class TestTcpTunnelBidirectional(unittest.TestCase):
    """Test bidirectional: outbound + inbound (TCP -> local UDP component)."""

    def setUp(self) -> None:
        self.tcp_port = _free_port()
        self.local_port = _free_port()
        self.server = _TcpServerHelper(self.tcp_port)

        self.tunnel = TcpTunnel(
            remote_host="127.0.0.1",
            remote_port=self.tcp_port,
            local_component_port=self.local_port,
            bidirectional=True,
        )
        self.tunnel.start()
        self.tunnel.wait_for_port(timeout=2.0)
        self.tcp_client = self.server.accept()

    def tearDown(self) -> None:
        self.tunnel.stop()
        self.server.close()

    def test_inbound_forwarding(self) -> None:
        """TCP data from remote arrives as UDP on local_component_port."""
        # Listen on the local component port
        udp_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_recv.bind(("127.0.0.1", self.local_port))
        udp_recv.settimeout(2.0)

        try:
            payload = b"hello from tcp"
            send_message(self.tcp_client, payload)

            data, addr = udp_recv.recvfrom(65535)
            self.assertEqual(data, payload)
            self.assertEqual(addr[0], "127.0.0.1")
        finally:
            udp_recv.close()

    def test_roundtrip(self) -> None:
        """Full roundtrip: UDP component -> TCP -> TCP -> UDP component."""
        # Listen on the local component port for inbound
        udp_component = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_component.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_component.bind(("127.0.0.1", self.local_port))
        udp_component.settimeout(2.0)

        try:
            # Component sends outbound via tunnel
            udp_component.sendto(
                b"command", ("127.0.0.1", self.tunnel.ephemeral_port)
            )

            # Remote receives it over TCP
            self.tcp_client.settimeout(2.0)
            data = recv_message(self.tcp_client)
            self.assertEqual(data, b"command")

            # Remote sends response over TCP
            send_message(self.tcp_client, b"response")

            # Component receives it via UDP
            data, _ = udp_component.recvfrom(65535)
            self.assertEqual(data, b"response")
        finally:
            udp_component.close()

    def test_multiple_roundtrips(self) -> None:
        """Multiple command-response roundtrips work correctly."""
        udp_component = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_component.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_component.bind(("127.0.0.1", self.local_port))
        udp_component.settimeout(2.0)

        try:
            self.tcp_client.settimeout(2.0)

            for i in range(5):
                cmd = f"cmd_{i}".encode()
                reply = f"reply_{i}".encode()

                udp_component.sendto(
                    cmd, ("127.0.0.1", self.tunnel.ephemeral_port)
                )
                data = recv_message(self.tcp_client)
                self.assertEqual(data, cmd)

                send_message(self.tcp_client, reply)
                data, _ = udp_component.recvfrom(65535)
                self.assertEqual(data, reply)
        finally:
            udp_component.close()


class TestTcpTunnelReconnect(unittest.TestCase):
    """Test reconnection behavior on TCP disconnect."""

    def test_reconnect_on_disconnect(self) -> None:
        """Tunnel reconnects after the remote side disconnects."""
        tcp_port = _free_port()
        local_port = _free_port()
        server = _TcpServerHelper(tcp_port)

        tunnel = TcpTunnel(
            remote_host="127.0.0.1",
            remote_port=tcp_port,
            local_component_port=local_port,
            bidirectional=False,
        )
        tunnel.start()
        tunnel.wait_for_port(timeout=2.0)

        try:
            # First connection
            client1 = server.accept()
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.sendto(b"first", ("127.0.0.1", tunnel.ephemeral_port))

            client1.settimeout(2.0)
            data = recv_message(client1)
            self.assertEqual(data, b"first")

            # Disconnect
            client1.close()

            # Wait for tunnel to detect disconnect and reconnect
            time.sleep(0.5)
            server.server_sock.settimeout(5.0)
            client2 = server.accept()

            # Send via reconnected tunnel
            udp.sendto(b"second", ("127.0.0.1", tunnel.ephemeral_port))

            client2.settimeout(2.0)
            data = recv_message(client2)
            self.assertEqual(data, b"second")

            udp.close()
            client2.close()
        finally:
            tunnel.stop()
            server.close()


class TestTcpTunnelHandshake(unittest.TestCase):
    """Test relay-mode handshake behavior."""

    def test_handshake_sent_on_connect(self) -> None:
        """Handshake bytes are sent first, response is read."""
        tcp_port = _free_port()
        local_port = _free_port()
        server = _TcpServerHelper(tcp_port)

        handshake_data = b"PeerAnnouncement:VIEWER:session123:VIDEO"

        tunnel = TcpTunnel(
            remote_host="127.0.0.1",
            remote_port=tcp_port,
            local_component_port=local_port,
            bidirectional=False,
            handshake=handshake_data,
        )
        tunnel.start()
        tunnel.wait_for_port(timeout=2.0)

        try:
            client = server.accept()
            client.settimeout(2.0)

            # Tunnel should have sent the handshake
            received = recv_message(client)
            self.assertEqual(received, handshake_data)

            # Send handshake response
            send_message(client, b"PeerInfo:session123")

            # Now data should flow
            time.sleep(0.2)
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.sendto(b"after_handshake", ("127.0.0.1", tunnel.ephemeral_port))

            data = recv_message(client)
            self.assertEqual(data, b"after_handshake")

            udp.close()
            client.close()
        finally:
            tunnel.stop()
            server.close()


class TestTcpTunnelLifecycle(unittest.TestCase):
    """Test start/stop lifecycle."""

    def test_clean_shutdown(self) -> None:
        """Tunnel shuts down cleanly while connected."""
        tcp_port = _free_port()
        local_port = _free_port()
        server = _TcpServerHelper(tcp_port)

        tunnel = TcpTunnel(
            remote_host="127.0.0.1",
            remote_port=tcp_port,
            local_component_port=local_port,
        )
        tunnel.start()
        tunnel.wait_for_port(timeout=2.0)

        client = server.accept()
        tunnel.stop()

        client.close()
        server.close()

    def test_stop_during_retry(self) -> None:
        """Tunnel stops cleanly while retrying connection."""
        tcp_port = _free_port()
        local_port = _free_port()
        # No server listening — tunnel will retry

        tunnel = TcpTunnel(
            remote_host="127.0.0.1",
            remote_port=tcp_port,
            local_component_port=local_port,
        )
        tunnel.start()
        tunnel.wait_for_port(timeout=2.0)

        # Let it retry a couple times
        time.sleep(0.5)

        # Stop should complete quickly
        tunnel.stop()

    def test_stop_before_start(self) -> None:
        """Stopping a tunnel that was never started does not crash."""
        tunnel = TcpTunnel("127.0.0.1", _free_port(), _free_port())
        tunnel.stop()

    def test_ephemeral_port_available_before_connect(self) -> None:
        """Ephemeral port is allocated even if TCP connect hasn't succeeded."""
        tcp_port = _free_port()
        # No server — connect will fail, but port should still be allocated

        tunnel = TcpTunnel(
            remote_host="127.0.0.1",
            remote_port=tcp_port,
            local_component_port=_free_port(),
        )
        tunnel.start()
        port = tunnel.wait_for_port(timeout=2.0)

        self.assertIsNotNone(port)
        self.assertGreater(port, 0)

        tunnel.stop()


if __name__ == "__main__":
    unittest.main()
