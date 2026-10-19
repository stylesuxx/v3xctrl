import unittest

from v3xctrl_e2e import artifacts
from v3xctrl_e2e.artifacts import format_failure, format_summary_table


def result(name: str, failures: list[str]) -> artifacts.TestResult:
    return artifacts.TestResult(name=name, passed=not failures, duration_seconds=38.1, failures=failures, notes=[])


class TestFormatSummaryTable(unittest.TestCase):
    def test_failures_sit_under_their_case_and_wrap_with_a_hanging_indent(self):
        long_failure = (
            "streamer failsafe during steady window: v3xctrl-control: "
            "2026-09-23 01:33:35,067 - ERROR - No message received for 0.15s"
        )
        table = format_summary_table(
            [result("L2-direct-tcp-tcp", [long_failure]), result("L4-mismatch", [])], width=100
        )

        self.assertEqual(
            table.splitlines(),
            [
                "test               result  seconds",
                "-----------------  ------  -------",
                "L2-direct-tcp-tcp  FAIL       38.1",
                "    - streamer failsafe during steady window",
                "      v3xctrl-control: 2026-09-23 01:33:35,067 - ERROR - No message received for 0.15s",
                "L4-mismatch        PASS       38.1",
                "",
                "1/2 passed",
            ],
        )
        self.assertTrue(all(len(line) <= 100 for line in table.splitlines()))

    def test_a_collapsed_failure_keeps_its_count_in_the_description(self):
        failure = (
            "streamer control error: 31 times from 00:22:05 to 00:26:19, first: v3xctrl-control: "
            "2026-09-23 00:22:05,443 - ERROR - No message received for 0.15s"
        )

        self.assertEqual(
            format_failure(failure, 100),
            [
                "    - streamer control error: 31 times from 00:22:05 to 00:26:19, first",
                "      v3xctrl-control: 2026-09-23 00:22:05,443 - ERROR - No message received for 0.15s",
            ],
        )

    def test_a_failure_without_a_quoted_line_wraps_as_one_bullet(self):
        self.assertEqual(
            format_failure("input: recording stopped: expected at least 1, saw 0", 100),
            ["    - input: recording stopped: expected at least 1, saw 0"],
        )

    def test_a_narrow_terminal_still_gets_a_readable_width(self):
        table = format_summary_table([result("L1", ["x " * 50])], width=20)

        self.assertTrue(all(len(line) <= 60 for line in table.splitlines()))
