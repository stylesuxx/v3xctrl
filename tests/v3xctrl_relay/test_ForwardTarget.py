import socket
import threading
import unittest
from unittest.mock import Mock, patch

from v3xctrl_relay.ForwardTarget import ForwardTarget, UdpTarget, TcpTarget


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
        mock_send.assert_called_once_with(sock, b"hello")
        self.assertTrue(target.is_alive())

    @patch("v3xctrl_relay.ForwardTarget.send_message", return_value=False)
    def test_send_failure_marks_dead(self, mock_send):
        sock = Mock(spec=socket.socket)
        target = TcpTarget(sock)

        self.assertFalse(target.send(b"hello"))
        self.assertFalse(target.is_alive())

    @patch("v3xctrl_relay.ForwardTarget.send_message", return_value=False)
    def test_send_after_dead_returns_false(self, mock_send):
        sock = Mock(spec=socket.socket)
        target = TcpTarget(sock)

        target.send(b"first")
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


if __name__ == "__main__":
    unittest.main()
