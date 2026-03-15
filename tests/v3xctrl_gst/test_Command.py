import unittest

from v3xctrl_gst.Command import (
    ActionType,
    Command,
    CommandValidationError,
    RecordingAction,
)


class TestActionType(unittest.TestCase):
    def test_action_type_values(self):
        self.assertEqual(ActionType.STOP, "stop")
        self.assertEqual(ActionType.LIST, "list")
        self.assertEqual(ActionType.GET, "get")
        self.assertEqual(ActionType.SET, "set")
        self.assertEqual(ActionType.RECORDING, "recording")
        self.assertEqual(ActionType.STATS, "stats")

    def test_action_type_is_str(self):
        self.assertIsInstance(ActionType.STOP, str)

    def test_action_type_membership(self):
        self.assertIn(ActionType.STOP, ActionType)
        self.assertIn(ActionType.SET, ActionType)
        self.assertEqual(len(ActionType), 6)


class TestRecordingAction(unittest.TestCase):
    def test_recording_action_values(self):
        self.assertEqual(RecordingAction.START, "start")
        self.assertEqual(RecordingAction.STOP, "stop")

    def test_recording_action_is_str(self):
        self.assertIsInstance(RecordingAction.START, str)


class TestCommandValidation(unittest.TestCase):
    def test_stop_action_requires_nothing(self):
        command = Command(action=ActionType.STOP)
        command.validate()

    def test_stats_action_requires_nothing(self):
        command = Command(action=ActionType.STATS)
        command.validate()

    def test_recording_action_valid_with_value(self):
        command = Command(action=ActionType.RECORDING, value=RecordingAction.START)
        command.validate()

    def test_recording_action_missing_value_raises(self):
        command = Command(action=ActionType.RECORDING)
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing value parameter", str(context.exception))

    def test_recording_action_empty_string_value_raises(self):
        command = Command(action=ActionType.RECORDING, value="")
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing value parameter", str(context.exception))

    def test_list_action_valid_with_element(self):
        command = Command(action=ActionType.LIST, element="encoder")
        command.validate()

    def test_list_action_missing_element_raises(self):
        command = Command(action=ActionType.LIST)
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing element parameter", str(context.exception))

    def test_get_action_valid(self):
        command = Command(action=ActionType.GET, element="encoder", property="bitrate")
        command.validate()

    def test_get_action_missing_element_raises(self):
        command = Command(action=ActionType.GET, property="bitrate")
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing element parameter", str(context.exception))

    def test_get_action_missing_property_raises(self):
        command = Command(action=ActionType.GET, element="encoder")
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing property parameter", str(context.exception))

    def test_set_action_valid(self):
        command = Command(action=ActionType.SET, element="encoder", property="bitrate", value=5000)
        command.validate()

    def test_set_action_missing_element_raises(self):
        command = Command(action=ActionType.SET, property="bitrate", value=5000)
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing element parameter", str(context.exception))

    def test_set_action_missing_property_raises(self):
        command = Command(action=ActionType.SET, element="encoder", value=5000)
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing property parameter", str(context.exception))

    def test_set_action_missing_value_raises(self):
        command = Command(action=ActionType.SET, element="encoder", property="bitrate")
        with self.assertRaises(CommandValidationError) as context:
            command.validate()
        self.assertIn("Missing value", str(context.exception))

    def test_set_action_value_zero_is_valid(self):
        command = Command(action=ActionType.SET, element="encoder", property="bitrate", value=0)
        command.validate()

    def test_set_action_value_false_is_valid(self):
        command = Command(action=ActionType.SET, element="encoder", property="enabled", value=False)
        command.validate()

    def test_stop_action_ignores_extra_fields(self):
        command = Command(action=ActionType.STOP, element="encoder", property="bitrate", value=5000)
        command.validate()

    def test_stats_action_ignores_extra_fields(self):
        command = Command(action=ActionType.STATS, element="encoder", property="bitrate")
        command.validate()

    def test_recording_action_ignores_element_and_property(self):
        command = Command(
            action=ActionType.RECORDING,
            element="encoder",
            property="bitrate",
            value=RecordingAction.STOP,
        )
        command.validate()


class TestCommandDataclass(unittest.TestCase):
    def test_default_values(self):
        command = Command(action=ActionType.STOP)
        self.assertIsNone(command.element)
        self.assertIsNone(command.property)
        self.assertIsNone(command.value)
        self.assertIsNone(command.properties)

    def test_all_fields(self):
        properties = {"key": "val"}
        command = Command(
            action=ActionType.SET,
            element="encoder",
            property="bitrate",
            value=5000,
            properties=properties,
        )
        self.assertEqual(command.action, ActionType.SET)
        self.assertEqual(command.element, "encoder")
        self.assertEqual(command.property, "bitrate")
        self.assertEqual(command.value, 5000)
        self.assertEqual(command.properties, properties)


if __name__ == "__main__":
    unittest.main()
