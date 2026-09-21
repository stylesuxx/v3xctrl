import unittest

from v3xctrl_e2e.matrix import ConnectionMode, Phase, build_matrix, needs_streamer, uses_relay

from v3xctrl_tcp.transport import Transport


class TestBuildMatrix(unittest.TestCase):
    def test_local_phase_without_negatives(self):
        cases = build_matrix({Phase.LOCAL}, include_negative=False)

        self.assertEqual([case.name for case in cases], ["L1-direct-udp-udp", "L2-direct-tcp-tcp"])
        self.assertTrue(all(case.mode == ConnectionMode.DIRECT for case in cases))
        self.assertTrue(all(case.is_expected_to_connect for case in cases))
        self.assertTrue(all(case.requires_streamer for case in cases))

    def test_viewer_phase_needs_no_streamer_and_runs_first(self):
        cases = build_matrix(set(Phase), include_negative=True)

        viewer_cases = [case for case in cases if case.phase == Phase.VIEWER]
        self.assertEqual([case.name for case in cases[: len(viewer_cases)]], [case.name for case in viewer_cases])
        self.assertEqual(
            [case.name for case in viewer_cases],
            [
                "V0-bootstrap",
                "V1-viewer-direct-tcp",
                "V2-viewer-relay-udp",
                "V3-viewer-relay-tcp",
                "V4-viewer-relay-wrong-id",
            ],
        )
        self.assertTrue(all(not case.requires_streamer for case in viewer_cases))
        self.assertFalse(viewer_cases[-1].is_expected_to_connect)

    def test_phase_requirements(self):
        self.assertFalse(needs_streamer({Phase.VIEWER}))
        self.assertTrue(needs_streamer({Phase.VIEWER, Phase.LOCAL}))
        self.assertTrue(uses_relay(build_matrix({Phase.VIEWER}, include_negative=False)))
        self.assertFalse(uses_relay(build_matrix({Phase.LOCAL}, include_negative=False)))

    def test_without_a_relay_id_the_relay_cases_are_dropped(self):
        cases = build_matrix({Phase.VIEWER}, include_negative=True, with_relay=False)

        self.assertEqual([case.name for case in cases], ["V0-bootstrap", "V1-viewer-direct-tcp"])

    def test_relay_phase_covers_all_transport_permutations(self):
        cases = build_matrix({Phase.RELAY}, include_negative=False)

        permutations = {(case.streamer_transport, case.viewer_transport) for case in cases}
        self.assertEqual(len(cases), 4)
        self.assertEqual(permutations, {(a, b) for a in Transport for b in Transport})

    def test_negatives_are_opt_in(self):
        cases = build_matrix(set(Phase), include_negative=True)

        negatives = [case for case in cases if not case.is_expected_to_connect]
        self.assertEqual(
            [case.name for case in negatives],
            [
                "V4-viewer-relay-wrong-id",
                "L3-direct-tcp-udp-mismatch",
                "L4-direct-udp-tcp-mismatch",
                "R5-relay-wrong-id",
            ],
        )
        self.assertTrue(negatives[3].wrong_relay_id)

    def test_only_l1_carries_the_input_and_fault_steps(self):
        cases = build_matrix(set(Phase), include_negative=True)

        with_extras = [case.name for case in cases if case.with_input_scenario or case.with_fault_injection]
        self.assertEqual(with_extras, ["L1-direct-udp-udp"])

    def test_only_v0_bootstraps_from_an_empty_config(self):
        cases = build_matrix(set(Phase), include_negative=True)

        bootstrapping = [case.name for case in cases if case.bootstrap_without_config]
        self.assertEqual(bootstrapping, ["V0-bootstrap"])


class TestSpectatorCases(unittest.TestCase):
    def test_spectator_cases_need_a_spectator_id(self):
        without = build_matrix({Phase.RELAY}, include_negative=False)
        with_spectator = build_matrix({Phase.RELAY}, include_negative=False, with_spectator=True)

        self.assertFalse(any(case.with_spectator for case in without))
        self.assertEqual(
            [case.name for case in with_spectator if case.with_spectator],
            [
                "R6-relay-udp-spectator",
                "R7-relay-tcp-spectator",
                "R8-relay-udp-spectator-after-viewer",
                "R9-relay-udp-viewer-leaves-spectator",
                "R10-relay-tcp-spectator-after-viewer",
            ],
        )

    def test_spectator_cases_come_before_the_negative_ones(self):
        names = [case.name for case in build_matrix({Phase.RELAY}, include_negative=True, with_spectator=True)]

        self.assertLess(names.index("R7-relay-tcp-spectator"), names.index("R5-relay-wrong-id"))
