import socket
import unittest

from v3xctrl_control.message import Heartbeat, Message
from v3xctrl_ui.network.VideoPortKeepAlive import (
    INTERVAL_STREAMING_S,
    VideoPortKeepAlive,
)


class TestVideoPortKeepAlive(unittest.TestCase):
    def setUp(self):
        # Simulate a relay by listening on a random port
        self.relay_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.relay_socket.bind(("127.0.0.1", 0))
        self.relay_socket.settimeout(3.0)
        self.relay_port = self.relay_socket.getsockname()[1]

    def tearDown(self):
        self.relay_socket.close()

    def test_interval_constants(self):
        self.assertEqual(INTERVAL_STREAMING_S, 30.0)

    def test_sends_heartbeat_to_relay(self):
        keep_alive = VideoPortKeepAlive(
            video_port=0,
            relay_host="127.0.0.1",
            relay_port=self.relay_port,
        )
        keep_alive.start()

        try:
            data, _ = self.relay_socket.recvfrom(1024)
            self.assertGreater(len(data), 0)

            message = Message.from_bytes(data)
            self.assertIsInstance(message, Heartbeat)
        finally:
            keep_alive.stop()
            keep_alive.join(timeout=3.0)

    def test_stops_cleanly(self):
        keep_alive = VideoPortKeepAlive(
            video_port=0,
            relay_host="127.0.0.1",
            relay_port=self.relay_port,
        )
        keep_alive.start()

        # Wait for at least one heartbeat
        self.relay_socket.recvfrom(1024)

        keep_alive.stop()
        keep_alive.join(timeout=3.0)
        self.assertFalse(keep_alive.is_alive())
