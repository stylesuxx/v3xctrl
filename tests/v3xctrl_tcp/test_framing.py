import socket
import struct
import threading
import unittest

from v3xctrl_tcp.framing import (
    HEADER_FORMAT,
    HEADER_SIZE,
    MAX_PAYLOAD_SIZE,
    recv_message,
    send_message,
)


def _make_socket_pair() -> tuple[socket.socket, socket.socket]:
    """Create a connected pair of TCP sockets for testing."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    peer, _ = server.accept()
    server.close()
    return client, peer


class TestSendMessage(unittest.TestCase):
    def setUp(self) -> None:
        self.sender, self.receiver = _make_socket_pair()

    def tearDown(self) -> None:
        self.sender.close()
        self.receiver.close()

    def test_send_and_recv_basic(self) -> None:
        payload = b"hello"
        self.assertTrue(send_message(self.sender, payload))
        result = recv_message(self.receiver)
        self.assertEqual(result, payload)

    def test_send_and_recv_empty_payload(self) -> None:
        self.assertTrue(send_message(self.sender, b""))
        result = recv_message(self.receiver)
        self.assertEqual(result, b"")

    def test_send_and_recv_max_size(self) -> None:
        payload = b"\xab" * MAX_PAYLOAD_SIZE
        self.assertTrue(send_message(self.sender, payload))
        result = recv_message(self.receiver)
        self.assertEqual(result, payload)

    def test_send_oversized_returns_false(self) -> None:
        payload = b"\x00" * (MAX_PAYLOAD_SIZE + 1)
        self.assertFalse(send_message(self.sender, payload))

    def test_send_to_closed_socket_returns_false(self) -> None:
        self.receiver.close()
        # May succeed on first send (kernel buffer), so send enough to fail
        result = True
        for _ in range(100):
            result = send_message(self.sender, b"x" * 10000)
            if not result:
                break
        self.assertFalse(result)

    def test_send_and_recv_multiple_messages(self) -> None:
        messages = [b"one", b"two", b"three", b""]
        for msg in messages:
            self.assertTrue(send_message(self.sender, msg))
        for msg in messages:
            result = recv_message(self.receiver)
            self.assertEqual(result, msg)

    def test_send_and_recv_binary_payload(self) -> None:
        payload = bytes(range(256))
        self.assertTrue(send_message(self.sender, payload))
        result = recv_message(self.receiver)
        self.assertEqual(result, payload)


class TestRecvMessage(unittest.TestCase):
    def setUp(self) -> None:
        self.sender, self.receiver = _make_socket_pair()

    def tearDown(self) -> None:
        self.sender.close()
        self.receiver.close()

    def test_recv_returns_none_on_clean_disconnect(self) -> None:
        self.sender.close()
        result = recv_message(self.receiver)
        self.assertIsNone(result)

    def test_recv_returns_none_on_partial_header(self) -> None:
        """Sender sends 1 byte of header then disconnects."""
        self.sender.sendall(b"\x00")
        self.sender.close()
        result = recv_message(self.receiver)
        self.assertIsNone(result)

    def test_recv_returns_none_on_partial_payload(self) -> None:
        """Sender sends header claiming 100 bytes but only sends 10."""
        header = struct.pack(HEADER_FORMAT, 100)
        self.sender.sendall(header + b"x" * 10)
        self.sender.close()
        result = recv_message(self.receiver)
        self.assertIsNone(result)

    def test_recv_handles_fragmented_send(self) -> None:
        """Simulate TCP fragmentation by sending byte-by-byte."""
        payload = b"fragmented"
        frame = struct.pack(HEADER_FORMAT, len(payload)) + payload

        def slow_send() -> None:
            for byte in frame:
                self.sender.sendall(bytes([byte]))

        t = threading.Thread(target=slow_send)
        t.start()
        result = recv_message(self.receiver)
        t.join()
        self.assertEqual(result, payload)


class TestFramingConstants(unittest.TestCase):
    def test_header_size_is_2(self) -> None:
        self.assertEqual(HEADER_SIZE, 2)

    def test_header_format_big_endian_unsigned_short(self) -> None:
        self.assertEqual(HEADER_FORMAT, "!H")

    def test_max_payload_size(self) -> None:
        self.assertEqual(MAX_PAYLOAD_SIZE, 65535)


if __name__ == "__main__":
    unittest.main()
