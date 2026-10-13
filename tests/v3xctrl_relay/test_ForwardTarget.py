import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch

from v3xctrl_relay.ForwardTarget import TcpTarget, UdpTarget
from v3xctrl_tcp.framing import recv_message
from v3xctrl_tcp.send_timeout import STREAM_SEND_TIMEOUT_MS


class TestUdpTarget(unittest.TestCase):
    def test_send_success(self):
        sock = Mock(spec=socket.socket)
        addr = ("1.2.3.4", 5000)
        target = UdpTarget(sock, addr)

        self.assertTrue(target.send(b"hello"))
        sock.sendto.assert_called_once_with(b"hello", addr)

    def test_send_failure(self):
        sock = Mock(spec=socket.socket)
        sock.sendto.side_effect = OSError("send failed")
        target = UdpTarget(sock, ("1.2.3.4", 5000))

        self.assertFalse(target.send(b"hello"))

    def test_is_alive(self):
        sock = Mock(spec=socket.socket)
        target = UdpTarget(sock, ("1.2.3.4", 5000))
        self.assertTrue(target.is_alive())


class TestTcpTarget(unittest.TestCase):
    @patch("v3xctrl_relay.ForwardTarget.send_message", return_value=True)
    def test_send_success(self, mock_send):
        sock = Mock(spec=socket.socket)
        target = TcpTarget(sock)

        self.assertTrue(target.send(b"hello"))
        self.assertTrue(_wait_until(lambda: mock_send.called, timeout=1.0))
        mock_send.assert_called_once_with(sock, b"hello")
        self.assertTrue(target.is_alive())

    @patch("v3xctrl_relay.ForwardTarget.send_message", return_value=False)
    def test_send_failure_marks_dead_and_shuts_the_connection_down(self, mock_send):
        sock = Mock(spec=socket.socket)
        target = TcpTarget(sock)

        target.send(b"hello")

        self.assertTrue(_wait_until(lambda: not target.is_alive(), timeout=1.0))
        sock.shutdown.assert_called_once_with(socket.SHUT_RDWR)

    @patch("v3xctrl_relay.ForwardTarget.send_message", return_value=False)
    def test_send_after_dead_returns_false(self, mock_send):
        sock = Mock(spec=socket.socket)
        target = TcpTarget(sock)

        target.send(b"first")
        self.assertTrue(_wait_until(lambda: not target.is_alive(), timeout=1.0))
        mock_send.reset_mock()

        self.assertFalse(target.send(b"second"))
        mock_send.assert_not_called()

    @patch("v3xctrl_relay.ForwardTarget.send_message", return_value=True)
    def test_concurrent_sends(self, mock_send):
        sock = Mock(spec=socket.socket)
        target = TcpTarget(sock)
        results = []

        def send_data(i):
            results.append(target.send(f"msg{i}".encode()))

        threads = [threading.Thread(target=send_data, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 10)
        self.assertTrue(all(results))

    def test_close(self):
        sock = Mock(spec=socket.socket)
        target = TcpTarget(sock)

        target.close()
        self.assertFalse(target.is_alive())
        sock.close.assert_called_once()

    def test_close_with_os_error(self):
        sock = Mock(spec=socket.socket)
        sock.close.side_effect = OSError
        target = TcpTarget(sock)

        target.close()  # Should not raise
        self.assertFalse(target.is_alive())


def _connected_pair() -> tuple[socket.socket, socket.socket]:
    """A loopback TCP connection with small buffers, so a peer that stops reading stalls the sender quickly."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    relay_side = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    relay_side.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    relay_side.connect(listener.getsockname())
    peer_side, _ = listener.accept()
    peer_side.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    listener.close()

    return relay_side, peer_side


def _wait_until(condition, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True

        time.sleep(0.01)

    return condition()


class TestTcpTargetStall(unittest.TestCase):
    PACKET = b"x" * 1400

    def setUp(self):
        self.relay_side, self.peer_side = _connected_pair()

    def tearDown(self):
        self.relay_side.close()
        self.peer_side.close()

    @patch("v3xctrl_relay.ForwardTarget.configure_send_timeout")
    def test_default_send_timeout_is_the_stream_timeout(self, mock_configure):
        sock = Mock(spec=socket.socket)
        TcpTarget(sock)

        mock_configure.assert_called_once_with(sock, STREAM_SEND_TIMEOUT_MS)

    def test_send_returns_at_once_while_the_peer_stalls(self):
        """The receive loop calls send; a peer that stops reading must not hold it up or kill the target."""
        target = TcpTarget(self.relay_side)

        started_at = time.monotonic()
        for _ in range(2000):
            target.send(self.PACKET)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 0.5)
        self.assertTrue(target.is_alive())
        target.close()

    def test_a_stalled_peer_is_disconnected(self):
        """Once the send timeout expires the peer must see the connection end, so it reconnects."""
        target = TcpTarget(self.relay_side, send_timeout_ms=100)

        for _ in range(2000):
            target.send(self.PACKET)

        self.assertTrue(_wait_until(lambda: not target.is_alive(), timeout=3.0))

        self.peer_side.settimeout(2.0)
        try:
            while self.peer_side.recv(65536):
                pass
        except ConnectionResetError:
            pass

    def test_packets_arrive_in_order(self):
        target = TcpTarget(self.relay_side)

        for index in range(300):
            target.send(index.to_bytes(2, "big"))

        self.peer_side.settimeout(2.0)
        received = [int.from_bytes(recv_message(self.peer_side), "big") for _ in range(300)]

        self.assertEqual(received, list(range(300)))
        target.close()


if __name__ == "__main__":
    unittest.main()
