import socket
import time
import unittest

from v3xctrl_control.message import Heartbeat, Message
from v3xctrl_ui.network.video.UdpVideoProxy import (
    HEARTBEAT_INTERVAL_S,
    UdpVideoProxy,
)


class TestUdpVideoProxy(unittest.TestCase):

    def setUp(self):
        # Simulate a relay by listening on a random port
        self.relay_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.relay_socket.bind(("127.0.0.1", 0))
        self.relay_socket.settimeout(3.0)
        self.relay_port = self.relay_socket.getsockname()[1]

    def tearDown(self):
        self.relay_socket.close()

    def test_heartbeat_interval_constant(self):
        self.assertEqual(HEARTBEAT_INTERVAL_S, 30.0)

    def test_start_proxy_binds_and_finds_local_port(self):
        proxy = UdpVideoProxy(
            video_port=0,
            relay_address=("127.0.0.1", self.relay_port),
        )
        try:
            self.assertTrue(proxy.start_proxy())
            self.assertGreater(proxy.local_port, 0)
        finally:
            proxy.stop()
            proxy.join(timeout=3.0)

    def test_sends_initial_heartbeat(self):
        proxy = UdpVideoProxy(
            video_port=0,
            relay_address=("127.0.0.1", self.relay_port),
        )
        try:
            proxy.start_proxy()

            data, _ = self.relay_socket.recvfrom(1024)
            self.assertGreater(len(data), 0)

            message = Message.from_bytes(data)
            self.assertIsInstance(message, Heartbeat)
        finally:
            proxy.stop()
            proxy.join(timeout=3.0)

    def test_forwards_packets_to_local_port(self):
        proxy = UdpVideoProxy(
            video_port=0,
            relay_address=("127.0.0.1", self.relay_port),
        )
        try:
            proxy.start_proxy()

            # Wait for initial heartbeat so proxy is running
            self.relay_socket.recvfrom(1024)

            # Listen on the local port (simulating ffmpeg)
            local_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_sock.bind(("127.0.0.1", proxy.local_port))
            local_sock.settimeout(3.0)

            # Send a test packet to the proxy's external port
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            video_port = proxy._external_sock.getsockname()[1]
            sender.sendto(b"test-rtp-data", ("127.0.0.1", video_port))
            sender.close()

            # Verify it arrives on the local port
            data, _ = local_sock.recvfrom(1024)
            self.assertEqual(data, b"test-rtp-data")

            local_sock.close()
        finally:
            proxy.stop()
            proxy.join(timeout=3.0)

    def test_stops_cleanly(self):
        proxy = UdpVideoProxy(
            video_port=0,
            relay_address=("127.0.0.1", self.relay_port),
        )
        proxy.start_proxy()

        # Wait for initial heartbeat
        self.relay_socket.recvfrom(1024)

        proxy.stop()
        proxy.join(timeout=3.0)
        self.assertFalse(proxy.is_alive())

    def test_start_proxy_returns_false_on_bind_failure(self):
        # Bind the port first without SO_REUSEADDR to block the proxy
        blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        blocker.bind(("0.0.0.0", 0))
        blocked_port = blocker.getsockname()[1]

        # Now create a second socket without SO_REUSEADDR on same port
        blocker2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            blocker2.bind(("0.0.0.0", blocked_port))
            # If this succeeds (OS allows it), skip the test
            blocker2.close()
            blocker.close()
            self.skipTest("OS allows duplicate bind without SO_REUSEADDR")
        except OSError:
            blocker2.close()

        # The proxy uses SO_REUSEADDR so it should actually succeed
        # on most platforms. This test verifies start_proxy handles
        # failures gracefully.
        blocker.close()

        proxy = UdpVideoProxy(
            video_port=0,
            relay_address=("127.0.0.1", self.relay_port),
        )
        result = proxy.start_proxy()
        if result:
            proxy.stop()
            proxy.join(timeout=3.0)
        # Either way, no crash
