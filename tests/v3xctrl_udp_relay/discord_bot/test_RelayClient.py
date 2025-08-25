import json
import socket
import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_udp_relay.discord_bot.RelayClient import RelayClient


class TestRelayClient(unittest.TestCase):
    def setUp(self):
        self.client = RelayClient()
        self.custom_client = RelayClient("/custom/socket/path")

    def test_init_default_values(self):
        client = RelayClient()
        self.assertEqual(client.socket_path, "/tmp/udp_relay_command.sock")
        self.assertEqual(client.timeout, 5.0)

    def test_init_custom_values(self):
        client = RelayClient("/custom/path")
        self.assertEqual(client.socket_path, "/custom/path")
        self.assertEqual(client.timeout, 5.0)

    def test_get_stats_calls_send_command(self):
        with patch.object(self.client, 'send_command', return_value={'test': 'data'}) as mock_send:
            result = self.client.get_stats()

            mock_send.assert_called_once_with(b"stats")
            self.assertEqual(result, {'test': 'data'})

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    def test_send_command_success(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b'{"status": "ok", "sessions": 3}'

        result = self.client.send_command(b"test_command")

        mock_socket_class.assert_called_once_with(socket.AF_UNIX, socket.SOCK_STREAM)
        mock_sock.settimeout.assert_called_once_with(5.0)
        mock_sock.connect.assert_called_once_with("/tmp/udp_relay_command.sock")
        mock_sock.send.assert_called_once_with(b"test_command")
        mock_sock.recv.assert_called_once_with(4096)
        mock_sock.close.assert_called_once()

        self.assertEqual(result, {"status": "ok", "sessions": 3})

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    def test_send_command_custom_socket_path(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b'{"result": "success"}'

        self.custom_client.send_command(b"command")

        mock_sock.connect.assert_called_once_with("/custom/socket/path")

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    @patch('logging.error')
    def test_send_command_connection_failure(self, mock_logging_error, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")

        with self.assertRaises(ConnectionRefusedError):
            self.client.send_command(b"test")

        mock_logging_error.assert_called_once_with("Failed to send command b'test': Connection refused")
        mock_sock.close.assert_called_once()

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    @patch('logging.error')
    def test_send_command_send_failure(self, mock_logging_error, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.side_effect = OSError("Send failed")

        with self.assertRaises(OSError):
            self.client.send_command(b"test")

        mock_logging_error.assert_called_once_with("Failed to send command b'test': Send failed")
        mock_sock.close.assert_called_once()

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    @patch('logging.error')
    def test_send_command_recv_failure(self, mock_logging_error, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = OSError("Recv failed")

        with self.assertRaises(OSError):
            self.client.send_command(b"test")

        mock_logging_error.assert_called_once_with("Failed to send command b'test': Recv failed")
        mock_sock.close.assert_called_once()

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    @patch('logging.error')
    def test_send_command_timeout(self, mock_logging_error, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = socket.timeout("Timeout")

        with self.assertRaises(socket.timeout):
            self.client.send_command(b"test")

        mock_logging_error.assert_called_once_with("Failed to send command b'test': Timeout")
        mock_sock.close.assert_called_once()

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    @patch('logging.error')
    def test_send_command_invalid_json(self, mock_logging_error, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b'invalid json{'

        with self.assertRaises(json.JSONDecodeError):
            self.client.send_command(b"test")

        mock_logging_error.assert_called_once()
        mock_sock.close.assert_called_once()

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    @patch('logging.error')
    def test_send_command_empty_response(self, mock_logging_error, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b''

        with self.assertRaises(json.JSONDecodeError):
            self.client.send_command(b"test")

        mock_logging_error.assert_called_once()
        mock_sock.close.assert_called_once()

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    def test_send_command_socket_close_called_even_on_success(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b'{"ok": true}'

        self.client.send_command(b"test")

        mock_sock.close.assert_called_once()

    @patch('v3xctrl_udp_relay.discord_bot.RelayClient.socket.socket')
    def test_send_command_socket_close_exception_ignored(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b'{"ok": true}'
        mock_sock.close.side_effect = OSError("Close failed")

        # Should not raise exception even if close fails
        result = self.client.send_command(b"test")
        self.assertEqual(result, {"ok": True})


if __name__ == '__main__':
    unittest.main()
