import tomllib
import unittest

from v3xctrl_e2e.matrix import LOCAL_CASES, RELAY_CASES, RELAY_NEGATIVE_CASES, WRONG_RELAY_ID
from v3xctrl_e2e.viewer_config import GamepadBinding, build_viewer_settings, render_settings

BINDING = GamepadBinding(
    guid="03000000",
    throttle_axis=1,
    steering_axis=0,
    brake_axis=2,
    trim_increase_button=2,
    trim_decrease_button=1,
    rec_toggle_button=0,
)


class TestBuildViewerSettings(unittest.TestCase):
    def test_direct_case_disables_relay(self):
        settings = build_viewer_settings(LOCAL_CASES[1], "relay.test:9999", "sid", None)

        self.assertEqual(settings["transport"], "tcp")
        self.assertFalse(settings["relay"]["enabled"])
        self.assertEqual(settings["ports"], {"video": 16384, "control": 16386})
        self.assertNotIn("input", settings)

    def test_relay_case_enables_relay_with_server_and_id(self):
        settings = build_viewer_settings(RELAY_CASES[2], "relay.test:9999", "sid", None)

        self.assertEqual(settings["transport"], "tcp")
        self.assertEqual(
            settings["relay"], {"enabled": True, "server": "relay.test:9999", "id": "sid", "spectator_mode": False}
        )

    def test_wrong_id_case(self):
        settings = build_viewer_settings(RELAY_NEGATIVE_CASES[0], "relay.test:9999", "sid", None)

        self.assertEqual(settings["relay"]["id"], WRONG_RELAY_ID)

    def test_gamepad_binding_writes_guid_and_calibration(self):
        settings = build_viewer_settings(LOCAL_CASES[1], "relay.test:9999", "sid", BINDING)

        self.assertEqual(settings["input"], {"guid": "03000000"})
        calibration = settings["calibrations"]["03000000"]
        self.assertEqual(calibration["throttle"]["axis"], 1)
        self.assertEqual(calibration["throttle"]["center"], 0.0)
        self.assertEqual(calibration["steering"]["axis"], 0)
        self.assertEqual(calibration["brake"]["axis"], 2)
        self.assertNotIn("center", calibration["brake"])
        self.assertEqual(calibration["buttons"], {"trim_increase": 2, "trim_decrease": 1, "rec_toggle": 0})

    def test_rendered_toml_round_trips(self):
        settings = build_viewer_settings(LOCAL_CASES[1], "relay.test:9999", "sid", BINDING)

        parsed = tomllib.loads(render_settings(settings))

        self.assertEqual(parsed, settings)
