import json
import socket
import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_gst.Command import ActionType, Command, RecordingAction
from v3xctrl_gst.ControlServer import ControlServer


class TestControlServerConstructor(unittest.TestCase):
    def test_handler_registry_contains_all_action_types(self):
        streamer = MagicMock()
        server = ControlServer(streamer)
        for action_type in ActionType:
            self.assertIn(action_type, server._command_handlers)

    def test_handler_registry_has_no_extra_keys(self):
        streamer = MagicMock()
        server = ControlServer(streamer)
        self.assertEqual(set(server._command_handlers.keys()), set(ActionType))

    def test_default_socket_path(self):
        streamer = MagicMock()
        server = ControlServer(streamer)
        self.assertEqual(server.socket_path, "/tmp/v3xctrl.sock")

    def test_custom_socket_path(self):
        streamer = MagicMock()
        server = ControlServer(streamer, socket_path="/tmp/custom.sock")
        self.assertEqual(server.socket_path, "/tmp/custom.sock")

    def test_initial_state(self):
        streamer = MagicMock()
        server = ControlServer(streamer)
        self.assertIsNone(server.server_socket)
        self.assertIsNone(server.thread)
        self.assertFalse(server.running)


class TestExecuteCommand(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_valid_action_dispatches_to_handler(self):
        command = Command(action=ActionType.STOP)
        self.streamer.stop.return_value = None
        result = self.server._execute_command(command)
        self.assertEqual(result["status"], "success")
        self.streamer.stop.assert_called_once()

    def test_unknown_action_returns_error(self):
        command = Command(action=ActionType.STOP)
        command.action = "nonexistent"
        result = self.server._execute_command(command)
        self.assertEqual(result["status"], "error")
        self.assertIn("nonexistent", result["message"])


class TestHandleStop(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_calls_streamer_stop(self):
        command = Command(action=ActionType.STOP)
        result = self.server._handle_stop(command)
        self.streamer.stop.assert_called_once()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"], "Pipeline stopped")


class TestHandleList(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_with_properties_returns_success(self):
        self.streamer.list_properties.return_value = {"brightness": 50, "contrast": 75}
        command = Command(action=ActionType.LIST, element="camera")
        result = self.server._handle_list(command)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["element"], "camera")
        self.assertEqual(result["properties"], {"brightness": 50, "contrast": 75})
        self.streamer.list_properties.assert_called_once_with("camera")

    def test_with_none_returns_error(self):
        self.streamer.list_properties.return_value = None
        command = Command(action=ActionType.LIST, element="missing_element")
        result = self.server._handle_list(command)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["element"], "missing_element")
        self.assertIsNone(result["properties"])


class TestHandleGet(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_with_value_returns_success(self):
        self.streamer.get_property.return_value = 42
        command = Command(action=ActionType.GET, element="encoder", property="bitrate")
        result = self.server._handle_get(command)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["element"], "encoder")
        self.assertEqual(result["property"], "bitrate")
        self.assertEqual(result["value"], 42)
        self.streamer.get_property.assert_called_once_with("encoder", "bitrate")

    def test_with_none_returns_error(self):
        self.streamer.get_property.return_value = None
        command = Command(action=ActionType.GET, element="encoder", property="missing")
        result = self.server._handle_get(command)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["element"], "encoder")
        self.assertEqual(result["property"], "missing")
        self.assertIsNone(result["value"])


class TestHandleSet(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_success(self):
        self.streamer.set_property.return_value = True
        self.streamer.get_property.return_value = 100
        command = Command(action=ActionType.SET, element="encoder", property="bitrate", value=100)
        result = self.server._handle_set(command)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["element"], "encoder")
        self.assertEqual(result["property"], "bitrate")
        self.assertEqual(result["value"], 100)
        self.streamer.set_property.assert_called_once_with("encoder", "bitrate", 100)
        self.streamer.get_property.assert_called_once_with("encoder", "bitrate")

    def test_failure(self):
        self.streamer.set_property.return_value = False
        self.streamer.get_property.return_value = 50
        command = Command(action=ActionType.SET, element="encoder", property="bitrate", value=100)
        result = self.server._handle_set(command)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["value"], 50)


class TestHandleRecording(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_start_success(self):
        self.streamer.start_recording.return_value = True
        command = Command(action=ActionType.RECORDING, value=RecordingAction.START)
        result = self.server._handle_recording(command)
        self.assertEqual(result["status"], "success")
        self.streamer.start_recording.assert_called_once()

    def test_start_failure(self):
        self.streamer.start_recording.return_value = False
        command = Command(action=ActionType.RECORDING, value=RecordingAction.START)
        result = self.server._handle_recording(command)
        self.assertEqual(result["status"], "error")

    def test_stop_success(self):
        self.streamer.stop_recording.return_value = True
        command = Command(action=ActionType.RECORDING, value=RecordingAction.STOP)
        result = self.server._handle_recording(command)
        self.assertEqual(result["status"], "success")
        self.streamer.stop_recording.assert_called_once()

    def test_stop_failure(self):
        self.streamer.stop_recording.return_value = False
        command = Command(action=ActionType.RECORDING, value=RecordingAction.STOP)
        result = self.server._handle_recording(command)
        self.assertEqual(result["status"], "error")

    def test_missing_value(self):
        command = Command(action=ActionType.RECORDING, value=None)
        result = self.server._handle_recording(command)
        self.assertEqual(result["status"], "error")
        self.assertIn("Missing value", result["message"])

    def test_unrecognized_value(self):
        command = Command(action=ActionType.RECORDING, value="pause")
        result = self.server._handle_recording(command)
        self.assertEqual(result["status"], "error")
        self.assertIn("Unrecognized value", result["message"])


class TestHandleStats(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_returns_streamer_stats(self):
        expected_stats = {"fps": 30, "bitrate": 5000, "dropped": 0}
        self.streamer.get_stats.return_value = expected_stats
        command = Command(action=ActionType.STATS)
        result = self.server._handle_stats(command)
        self.assertEqual(result, expected_stats)
        self.streamer.get_stats.assert_called_once()


class TestHandleClient(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)
        self.server.running = True

    def _make_mock_socket(self, messages: list[bytes]):
        client_socket = MagicMock(spec=socket.socket)
        client_socket.recv.side_effect = messages
        return client_socket

    def test_valid_json_command(self):
        command_data = json.dumps({"action": "stop"}).encode("utf-8")
        client_socket = self._make_mock_socket([command_data, b""])
        with patch.object(Command, "validate"):
            self.server._handle_client(client_socket)
        self.streamer.stop.assert_called_once()
        client_socket.sendall.assert_called_once()
        response = json.loads(client_socket.sendall.call_args[0][0].decode("utf-8").strip())
        self.assertEqual(response["status"], "success")
        client_socket.close.assert_called_once()

    def test_invalid_json(self):
        client_socket = self._make_mock_socket([b"not valid json", b""])
        self.server._handle_client(client_socket)
        client_socket.sendall.assert_called_once()
        response = json.loads(client_socket.sendall.call_args[0][0].decode("utf-8").strip())
        self.assertEqual(response["status"], "error")
        self.assertIn("Invalid JSON", response["message"])
        client_socket.close.assert_called_once()

    def test_validation_error(self):
        command_data = json.dumps({"action": "get"}).encode("utf-8")
        client_socket = self._make_mock_socket([command_data, b""])
        self.server._handle_client(client_socket)
        client_socket.sendall.assert_called_once()
        response = json.loads(client_socket.sendall.call_args[0][0].decode("utf-8").strip())
        self.assertEqual(response["status"], "error")
        client_socket.close.assert_called_once()

    def test_empty_data_disconnect(self):
        client_socket = self._make_mock_socket([b""])
        self.server._handle_client(client_socket)
        client_socket.sendall.assert_not_called()
        client_socket.close.assert_called_once()


class TestSerializeValue(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_none(self):
        self.assertIsNone(self.server._serialize_value(None))

    def test_string(self):
        self.assertEqual(self.server._serialize_value("hello"), "hello")

    def test_int(self):
        self.assertEqual(self.server._serialize_value(42), 42)

    def test_float(self):
        self.assertEqual(self.server._serialize_value(3.14), 3.14)

    def test_bool(self):
        self.assertIs(self.server._serialize_value(True), True)
        self.assertIs(self.server._serialize_value(False), False)

    def test_list(self):
        result = self.server._serialize_value([1, "two", 3.0])
        self.assertEqual(result, [1, "two", 3.0])

    def test_tuple(self):
        result = self.server._serialize_value((1, 2, 3))
        self.assertEqual(result, [1, 2, 3])

    def test_nested_list(self):
        result = self.server._serialize_value([[1, 2], [3, 4]])
        self.assertEqual(result, [[1, 2], [3, 4]])

    def test_dict(self):
        result = self.server._serialize_value({"key": "value", "num": 5})
        self.assertEqual(result, {"key": "value", "num": 5})

    def test_nested_dict(self):
        result = self.server._serialize_value({"outer": {"inner": 42}})
        self.assertEqual(result, {"outer": {"inner": 42}})

    def test_non_serializable_object(self):
        obj = object()
        result = self.server._serialize_value(obj)
        self.assertEqual(result, str(obj))

    def test_custom_class_instance(self):
        class Custom:
            def __str__(self):
                return "custom_repr"

        result = self.server._serialize_value(Custom())
        self.assertEqual(result, "custom_repr")


class TestSerializeProperties(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_none(self):
        self.assertIsNone(self.server._serialize_properties(None))

    def test_dict(self):
        result = self.server._serialize_properties({"brightness": 50, "contrast": 75})
        self.assertEqual(result, {"brightness": 50, "contrast": 75})

    def test_dict_with_non_serializable_values(self):
        obj = object()
        result = self.server._serialize_properties({"key": obj})
        self.assertEqual(result, {"key": str(obj)})

    def test_non_dict(self):
        result = self.server._serialize_properties("some string")
        self.assertEqual(result, "some string")

    def test_non_dict_object(self):
        result = self.server._serialize_properties(42)
        self.assertEqual(result, "42")


class TestStop(unittest.TestCase):
    def setUp(self):
        self.streamer = MagicMock()
        self.server = ControlServer(self.streamer)

    def test_closes_socket_and_unlinks_path(self):
        mock_socket = MagicMock(spec=socket.socket)
        self.server.server_socket = mock_socket
        self.server.running = True
        with patch("os.path.exists", return_value=True) as mock_exists, patch("os.unlink") as mock_unlink:
            self.server.stop()
            self.assertFalse(self.server.running)
            mock_socket.close.assert_called_once()
            mock_exists.assert_called_once_with(self.server.socket_path)
            mock_unlink.assert_called_once_with(self.server.socket_path)

    def test_handles_no_socket(self):
        self.server.server_socket = None
        with patch("os.path.exists", return_value=False):
            self.server.stop()
            self.assertFalse(self.server.running)

    def test_handles_socket_close_error(self):
        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.close.side_effect = OSError("socket error")
        self.server.server_socket = mock_socket
        with patch("os.path.exists", return_value=False):
            self.server.stop()
            self.assertFalse(self.server.running)

    def test_handles_unlink_error(self):
        self.server.server_socket = None
        with patch("os.path.exists", return_value=True), patch("os.unlink", side_effect=OSError("unlink error")):
            self.server.stop()
            self.assertFalse(self.server.running)

    def test_handles_missing_path(self):
        self.server.server_socket = None
        with patch("os.path.exists", return_value=False) as mock_exists:
            self.server.stop()
            self.assertFalse(self.server.running)
            mock_exists.assert_called_once_with(self.server.socket_path)


if __name__ == "__main__":
    unittest.main()
