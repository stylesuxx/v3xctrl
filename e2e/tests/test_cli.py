import tempfile
import unittest
from unittest.mock import patch

from v3xctrl_e2e.cli import EXIT_PREFLIGHT, _interrupt_on_terminate, main, parse_arguments, skipped_case_groups
from v3xctrl_e2e.matrix import Phase
from v3xctrl_e2e.streamer_client import AgentError
from v3xctrl_e2e.viewer_launcher import ViewerKind

BASE = ["--streamer-host", "192.168.1.225", "--ssh-user", "chris"]


class TestParseArguments(unittest.TestCase):
    def test_relay_id_is_required_for_the_relay_phase(self):
        with self.assertRaises(SystemExit):
            parse_arguments(BASE)

    def test_viewer_phase_needs_neither_streamer_nor_relay_id(self):
        options = parse_arguments(["--only", "viewer"])

        self.assertEqual(options.phases, {Phase.VIEWER})
        self.assertIsNone(options.streamer_host)
        assert options.viewer_source is not None
        self.assertEqual(options.viewer_source.name, "src")

    def test_viewer_source_can_point_at_another_checkout(self):
        options = parse_arguments(["--only", "viewer", "--relay-id", "abc", "--viewer-source", "/tmp/other/src"])

        self.assertEqual(str(options.viewer_source), "/tmp/other/src")

    def test_streamer_phases_need_a_streamer(self):
        with self.assertRaises(SystemExit):
            parse_arguments(["--only", "local"])

    def test_only_can_be_repeated(self):
        options = parse_arguments([*BASE, "--only", "local", "--only", "relay", "--relay-id", "abc"])

        self.assertEqual(options.phases, {Phase.LOCAL, Phase.RELAY})

    def test_spectator_options(self):
        options = parse_arguments(
            [*BASE, "--only", "relay", "--relay-id", "abc", "--spectator-id", "spec", "--spectator-seconds", "90"]
        )

        self.assertEqual(options.spectator_id, "spec")
        self.assertEqual(options.spectator_seconds, 90.0)

    def test_skipped_groups_are_named(self):
        options = parse_arguments([*BASE, "--relay-id", "abc"])

        self.assertEqual(
            skipped_case_groups(options),
            ["the negative cases (add --negative)", "the spectator cases (add --spectator-id)"],
        )

    def test_full_run_skips_nothing(self):
        options = parse_arguments([*BASE, "--relay-id", "abc", "--spectator-id", "spec", "--negative"])

        self.assertEqual(skipped_case_groups(options), [])

    def test_explicit_cases_skip_nothing(self):
        options = parse_arguments([*BASE, "--only", "local", "--case", "L1-direct-udp-udp"])

        self.assertEqual(skipped_case_groups(options), [])

    def test_case_filter_is_repeatable(self):
        options = parse_arguments(
            [*BASE, "--only", "local", "--case", "L1-direct-udp-udp", "--case", "L2-direct-tcp-tcp"]
        )

        self.assertEqual(options.case_names, ["L1-direct-udp-udp", "L2-direct-tcp-tcp"])

    def test_short_steady_window_is_refused(self):
        with self.assertRaises(SystemExit):
            parse_arguments([*BASE, "--only", "local", "--steady-seconds", "10"])

    def test_spectator_defaults(self):
        options = parse_arguments([*BASE, "--only", "local"])

        self.assertEqual(options.spectator_id, "")
        self.assertEqual(options.spectator_seconds, 60.0)

    def test_local_only_needs_no_relay_id(self):
        options = parse_arguments([*BASE, "--only", "local"])

        self.assertEqual(options.phases, {Phase.LOCAL})
        self.assertEqual(options.viewer_kind, ViewerKind.SOURCE)
        self.assertTrue(options.with_gamepad)
        self.assertFalse(options.use_camera)

    def test_full_run_options(self):
        options = parse_arguments(
            [
                *BASE,
                "--relay-id",
                "abc",
                "--viewer",
                "flatpak",
                "--camera",
                "--without-gamepad",
                "--negative",
                "--min-fps",
                "20",
            ]
        )

        self.assertEqual(options.phases, set(Phase))
        self.assertEqual(options.viewer_kind, ViewerKind.FLATPAK)
        self.assertTrue(options.use_camera)
        self.assertFalse(options.with_gamepad)
        self.assertTrue(options.include_negative)
        self.assertEqual(options.minimum_fps, 20)


class TestTerminate(unittest.TestCase):
    def test_sigterm_unwinds_like_an_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):
            _interrupt_on_terminate(15, None)


class TestMain(unittest.TestCase):
    def test_unreachable_streamer_is_a_preflight_failure(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("v3xctrl_e2e.cli.deploy_agent", side_effect=AgentError("copying the agent took too long")),
            patch("v3xctrl_e2e.cli.close_control_master") as close,
        ):
            exit_code = main([*BASE, "--only", "local", "--runs-directory", directory])

        self.assertEqual(exit_code, EXIT_PREFLIGHT)
        close.assert_called_once()
