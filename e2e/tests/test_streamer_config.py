import copy
import unittest

from v3xctrl_e2e.matrix import LOCAL_CASES, RELAY_CASES, RELAY_NEGATIVE_CASES, WRONG_RELAY_ID
from v3xctrl_e2e.streamer_config import (
    build_streamer_config,
    load_shipped_defaults,
    recording_directory,
    source_framerate,
    telemetry_send_rate,
)

LIVE_CONFIG = {
    "network": {"wifi": {"ssid": "home", "password": "secret"}, "routing": "wlan"},
    "viewer": {
        "mode": "relay",
        "transport": "tcp",
        "direct": {"host": "10.0.0.5"},
        "relay": {"host": "old.example:1", "sessionId": "old"},
        "ports": {"video": 1, "control": 2},
    },
    "video": {"resolution": "1920x1080@25", "testSource": False, "record": {"path": "/data/rec"}},
    "telemetry": {"sendRate": 2.0},
    "development": {"logLevel": "ERROR"},
}


class TestBuildStreamerConfig(unittest.TestCase):
    def setUp(self):
        self.shipped = load_shipped_defaults()

    def test_viewer_section_is_reset_to_shipped_defaults_then_patched(self):
        case = next(case for case in LOCAL_CASES if case.name == "L2-direct-tcp-tcp")

        config = build_streamer_config(LIVE_CONFIG, self.shipped, case, "192.168.1.100", "relay.test:9999", "sid")

        self.assertEqual(config["viewer"]["mode"], "direct")
        self.assertEqual(config["viewer"]["transport"], "tcp")
        self.assertEqual(config["viewer"]["direct"]["host"], "192.168.1.100")
        self.assertEqual(config["viewer"]["relay"], {"host": "relay.test:9999", "sessionId": "sid"})
        self.assertEqual(config["viewer"]["ports"], self.shipped["viewer"]["ports"])

    def test_relay_case(self):
        case = next(case for case in RELAY_CASES if case.name == "R1-relay-udp-udp")

        config = build_streamer_config(LIVE_CONFIG, self.shipped, case, "192.168.1.100", "relay.test:9999", "sid")

        self.assertEqual(config["viewer"]["mode"], "relay")
        self.assertEqual(config["viewer"]["transport"], "udp")

    def test_wrong_id_case_uses_the_sentinel_id(self):
        case = RELAY_NEGATIVE_CASES[0]

        config = build_streamer_config(LIVE_CONFIG, self.shipped, case, "192.168.1.100", "relay.test:9999", "sid")

        self.assertEqual(config["viewer"]["relay"]["sessionId"], WRONG_RELAY_ID)

    def test_network_section_is_never_touched(self):
        live = copy.deepcopy(LIVE_CONFIG)

        config = build_streamer_config(live, self.shipped, LOCAL_CASES[1], "192.168.1.100", "relay.test:9999", "sid")

        self.assertEqual(config["network"], LIVE_CONFIG["network"])
        self.assertEqual(live, LIVE_CONFIG)

    def test_debug_logging_and_test_source_are_forced(self):
        config = build_streamer_config(
            LIVE_CONFIG, self.shipped, LOCAL_CASES[1], "192.168.1.100", "relay.test:9999", "sid"
        )

        self.assertEqual(config["development"]["logLevel"], "DEBUG")
        self.assertTrue(config["video"]["testSource"])
        self.assertTrue(config["video"]["autostart"])

    def test_camera_runs_switch_the_test_source_off(self):
        config = build_streamer_config(
            LIVE_CONFIG,
            self.shipped,
            LOCAL_CASES[1],
            "192.168.1.100",
            "relay.test:9999",
            "sid",
            use_camera=True,
        )

        self.assertFalse(config["video"]["testSource"])
        self.assertTrue(config["video"]["autostart"])


class TestConfigReaders(unittest.TestCase):
    def test_send_rate_and_framerate_and_recording_directory(self):
        self.assertEqual(telemetry_send_rate(LIVE_CONFIG), 2.0)
        self.assertEqual(source_framerate(LIVE_CONFIG), 25)
        self.assertEqual(recording_directory(LIVE_CONFIG), "/data/rec")

    def test_defaults_when_keys_are_missing(self):
        self.assertEqual(telemetry_send_rate({}), 1.0)
        self.assertEqual(source_framerate({"video": {"resolution": "640x480"}}), 30)
        self.assertEqual(recording_directory({}), "/data/recordings")
