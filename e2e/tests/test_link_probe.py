import subprocess
import unittest

from v3xctrl_e2e.link_probe import LinkReport, parse_ping_output, ping_command, probe_from_here, relay_address

IPUTILS_SUMMARY = (
    "--- relay.v3xctrl.com ping statistics ---\n"
    "50 packets transmitted, 46 received, 8% packet loss, time 9812ms\n"
    "rtt min/avg/max/mdev = 15.377/66.101/153.145/61.829 ms\n"
)
BUSYBOX_SUMMARY = "5 packets transmitted, 5 packets received, 0% packet loss\nround-trip min/avg/max = 1.0/2.0/3.0 ms\n"


class TestParsePing(unittest.TestCase):
    def test_iputils_summary(self):
        quality = parse_ping_output(IPUTILS_SUMMARY)

        assert quality is not None
        self.assertEqual((quality.sent, quality.received), (50, 46))
        self.assertAlmostEqual(quality.loss_percent, 8.0)
        self.assertEqual(quality.describe(), "8.0% loss, rtt avg 66 ms, max 153 ms, jitter 62 ms")

    def test_no_answer_at_all(self):
        quality = parse_ping_output("50 packets transmitted, 0 received, 100% packet loss, time 9800ms\n")

        assert quality is not None
        self.assertEqual(quality.describe(), "no answer to 50 pings")

    def test_counts_without_rtt_line(self):
        quality = parse_ping_output(BUSYBOX_SUMMARY)

        assert quality is not None
        self.assertEqual(quality.received, 5)
        self.assertIsNone(quality.rtt_average_ms)

    def test_unparseable_output(self):
        self.assertIsNone(parse_ping_output("ping: unknown host relay.test\n"))


class TestProbe(unittest.TestCase):
    def test_command_spreads_the_pings_over_the_seconds(self):
        self.assertEqual(
            ping_command("relay.test", 10.0), ["ping", "-q", "-n", "-i", "0.2", "-c", "50", "-w", "15", "relay.test"]
        )

    def test_probe_parses_the_runner_output(self):
        def runner(arguments, **kwargs):
            return subprocess.CompletedProcess(arguments, 0, stdout=IPUTILS_SUMMARY, stderr="")

        quality = probe_from_here("relay.test", 10.0, runner=runner)

        assert quality is not None
        self.assertEqual(quality.received, 46)

    def test_a_missing_ping_binary_reports_nothing(self):
        def runner(arguments, **kwargs):
            raise FileNotFoundError("ping")

        self.assertIsNone(probe_from_here("relay.test", 10.0, runner=runner))

    def test_failed_probe_is_named(self):
        self.assertEqual(
            LinkReport("viewer to relay", "relay.test", None).describe(), "viewer to relay (relay.test): probe failed"
        )

    def test_relay_address_drops_the_port(self):
        self.assertEqual(relay_address("relay.v3xctrl.com:8888"), "relay.v3xctrl.com")
