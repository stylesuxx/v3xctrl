import unittest

from v3xctrl_e2e.expectations import expectations_for, failure_expectations_for
from v3xctrl_e2e.log_expectations import LogSource
from v3xctrl_e2e.matrix import (
    LOCAL_CASES,
    LOCAL_NEGATIVE_CASES,
    RELAY_CASES,
    RELAY_NEGATIVE_CASES,
    SPECTATOR_CASES,
    VIEWER_CASES,
    VIEWER_NEGATIVE_CASES,
)


def by_name(cases, name):
    return next(case for case in cases if case.name == name)


def patterns(required):
    return [requirement.pattern for requirement in required]


class TestExpectationsFor(unittest.TestCase):
    def test_direct_udp_has_the_baseline_only(self):
        expectations = expectations_for(by_name(LOCAL_CASES, "L1-direct-udp-udp"), with_gamepad=False)

        self.assertIn(r"Control channel connected", patterns(expectations.connection))
        self.assertIn(r"First telemetry message received", patterns(expectations.connection))
        self.assertNotIn(r"New gamepad detected", patterns(expectations.connection))
        self.assertNotIn(r"TcpTunnel connected to", patterns(expectations.run))
        self.assertNotIn(r"Received PeerInfo for video:", patterns(expectations.connection))

    def test_gamepad_lines_are_required_when_a_gamepad_is_bound(self):
        expectations = expectations_for(by_name(LOCAL_CASES, "L1-direct-udp-udp"), with_gamepad=True)

        self.assertIn(r"New gamepad detected", patterns(expectations.connection))
        self.assertIn(r"Found default gamepad", patterns(expectations.connection))

    def test_direct_tcp_requires_servers_and_tunnels(self):
        expectations = expectations_for(by_name(LOCAL_CASES, "L2-direct-tcp-tcp"), with_gamepad=False)

        self.assertIn(r"TCP server listening on port", patterns(expectations.connection))
        self.assertIn(r"TCP client connected on port", patterns(expectations.connection))
        tunnels = [requirement for requirement in expectations.run if requirement.pattern == r"TcpTunnel connected to"]
        self.assertEqual({requirement.source for requirement in tunnels}, {LogSource.VIDEO, LogSource.CONTROL})

    def test_relay_udp_viewer_waits_for_peer_info(self):
        expectations = expectations_for(by_name(RELAY_CASES, "R1-relay-udp-udp"), with_gamepad=False)

        self.assertIn(r"Received PeerInfo for video:", patterns(expectations.connection))
        self.assertIn(r"Received PeerInfo for video:", patterns(expectations.run))

    def test_relay_tcp_viewer_waits_for_tunnel_handshakes(self):
        expectations = expectations_for(by_name(RELAY_CASES, "R2-relay-tcp-tcp"), with_gamepad=False)

        self.assertIn(r"TCP relay tunnels started \(video \+ control\)", patterns(expectations.connection))
        self.assertIn(r"TcpTunnel handshake complete", patterns(expectations.run))

    def test_mixed_relay_transports_combine_both_sides(self):
        expectations = expectations_for(by_name(RELAY_CASES, "R4-relay-tcp-udp"), with_gamepad=False)

        self.assertIn(r"Received PeerInfo for video:", patterns(expectations.connection))
        self.assertIn(r"TcpTunnel handshake complete", patterns(expectations.run))

    def test_negative_cases_have_no_positive_expectations(self):
        expectations = expectations_for(by_name(LOCAL_NEGATIVE_CASES, "L3-direct-tcp-udp-mismatch"), with_gamepad=True)

        self.assertEqual(expectations.connection, [])
        self.assertEqual(expectations.forbidden, [])


class TestViewerOnlyExpectations(unittest.TestCase):
    def test_bootstrap_only_needs_the_receiver(self):
        expectations = expectations_for(by_name(VIEWER_CASES, "V0-bootstrap"), with_gamepad=True)

        self.assertEqual(
            patterns(expectations.connection), [r"Using gst video receiver", r"GStreamer receiver started on port"]
        )
        self.assertEqual(expectations.run, [])
        self.assertNotIn(r"New gamepad detected", patterns(expectations.connection))

    def test_direct_tcp_only_needs_listening_servers(self):
        expectations = expectations_for(by_name(VIEWER_CASES, "V1-viewer-direct-tcp"), with_gamepad=False)

        self.assertIn(r"TCP server listening on port", patterns(expectations.connection))
        self.assertNotIn(r"TCP client connected on port", patterns(expectations.connection))

    def test_relay_udp_proves_announcements_only(self):
        expectations = expectations_for(by_name(VIEWER_CASES, "V2-viewer-relay-udp"), with_gamepad=False)

        self.assertIn(r"Sent video announcement to", patterns(expectations.connection))
        self.assertNotIn(r"Using gst video receiver", patterns(expectations.connection))
        self.assertNotIn(r"Received PeerInfo for video:", patterns(expectations.connection))

    def test_relay_tcp_proves_tunnels_start_and_connects_never_fail(self):
        expectations = expectations_for(by_name(VIEWER_CASES, "V3-viewer-relay-tcp"), with_gamepad=False)

        self.assertIn(r"TcpTunnel UDP proxy bound on ephemeral port", patterns(expectations.connection))
        self.assertIn(r"Using gst video receiver", patterns(expectations.connection))
        self.assertNotIn(r"TcpTunnel connected to", patterns(expectations.connection))
        self.assertIn(r"TCP connect failed", [rule.pattern for rule in expectations.forbidden])

    def test_relay_failures_are_forbidden_throughout(self):
        expectations = expectations_for(by_name(VIEWER_CASES, "V2-viewer-relay-udp"), with_gamepad=False)

        self.assertIn(r"Relay setup failed", [rule.pattern for rule in expectations.steady_forbidden])
        self.assertIn(r"Response Error", [rule.pattern for rule in expectations.forbidden])

    def test_wrong_id_waits_on_the_viewer_only(self):
        required = failure_expectations_for(by_name(VIEWER_NEGATIVE_CASES, "V4-viewer-relay-wrong-id"))

        self.assertEqual([requirement.source for requirement in required], [LogSource.VIEWER])


class TestSpectatorExpectations(unittest.TestCase):
    def test_udp_spectator_waits_for_peer_info_and_video(self):
        expectations = expectations_for(by_name(SPECTATOR_CASES, "R6-relay-udp-spectator"), with_gamepad=False)

        spectator = expectations.spectator_connection
        self.assertTrue(all(requirement.source == LogSource.SPECTATOR for requirement in spectator))
        self.assertIn(r"Received PeerInfo for video:", patterns(spectator))
        self.assertIn(r"Pipeline is now PLAYING", patterns(spectator))
        self.assertIn(
            r"No frames received for",
            [rule.pattern for rule in expectations.steady_forbidden if rule.source == LogSource.SPECTATOR],
        )

    def test_tcp_spectator_waits_for_tunnel_handshakes(self):
        expectations = expectations_for(by_name(SPECTATOR_CASES, "R7-relay-tcp-spectator"), with_gamepad=False)

        self.assertIn(r"TcpTunnel handshake complete", patterns(expectations.spectator_connection))

    def test_replacing_spectator_expects_the_streamer_to_lose_its_viewer(self):
        expectations = expectations_for(
            by_name(SPECTATOR_CASES, "R8-relay-udp-spectator-after-viewer"), with_gamepad=False
        )

        self.assertFalse(any(rule.source == LogSource.CONTROL for rule in expectations.forbidden))
        self.assertTrue(all(rule.source == LogSource.SPECTATOR for rule in expectations.steady_forbidden))
        self.assertIn(r"Received PeerInfo for video:", patterns(expectations.spectator_connection))

    def test_plain_cases_have_no_spectator_expectations(self):
        expectations = expectations_for(by_name(RELAY_CASES, "R1-relay-udp-udp"), with_gamepad=False)

        self.assertEqual(expectations.spectator_connection, [])
        self.assertFalse(any(rule.source == LogSource.SPECTATOR for rule in expectations.forbidden))


class TestFailureExpectations(unittest.TestCase):
    def test_wrong_id_waits_on_both_sides(self):
        required = failure_expectations_for(by_name(RELAY_NEGATIVE_CASES, "R5-relay-wrong-id"))

        self.assertEqual(
            {requirement.source for requirement in required}, {LogSource.SERVICE_MANAGER, LogSource.VIEWER}
        )

    def test_tcp_mismatch_waits_on_the_video_service(self):
        required = failure_expectations_for(by_name(LOCAL_NEGATIVE_CASES, "L3-direct-tcp-udp-mismatch"))

        self.assertEqual([requirement.source for requirement in required], [LogSource.VIDEO])

    def test_udp_into_tcp_has_nothing_to_wait_for(self):
        self.assertEqual(failure_expectations_for(by_name(LOCAL_NEGATIVE_CASES, "L4-direct-udp-tcp-mismatch")), [])

    def test_positive_case_has_no_failure_expectations(self):
        self.assertEqual(failure_expectations_for(by_name(LOCAL_CASES, "L1-direct-udp-udp")), [])
