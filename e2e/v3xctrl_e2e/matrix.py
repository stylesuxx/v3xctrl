"""The permutations the harness runs, and what each one is expected to prove."""

from dataclasses import dataclass
from enum import StrEnum

from v3xctrl_e2e.log_expectations import LogSource
from v3xctrl_tcp.transport import Transport


class ConnectionMode(StrEnum):
    DIRECT = "direct"
    RELAY = "relay"


class Phase(StrEnum):
    VIEWER = "viewer"
    LOCAL = "local"
    RELAY = "relay"


WRONG_RELAY_ID = "e2e-wrong-session-id"


@dataclass(frozen=True)
class ExpectedFailure:
    """A negative test passes when these lines show up and no connection is made."""

    description: str
    streamer_pattern: str | None = None
    streamer_source: LogSource = LogSource.VIDEO
    viewer_pattern: str | None = None


@dataclass(frozen=True)
class TestCase:
    name: str
    phase: Phase
    mode: ConnectionMode
    streamer_transport: Transport
    viewer_transport: Transport
    requires_streamer: bool = True
    bootstrap_without_config: bool = False
    with_input_scenario: bool = False
    with_fault_injection: bool = False
    wrong_relay_id: bool = False
    with_spectator: bool = False
    spectator_replaces_viewer: bool = False
    viewer_leaves_after_spectator: bool = False
    expected_failure: ExpectedFailure | None = None

    @property
    def is_expected_to_connect(self) -> bool:
        return self.expected_failure is None


TCP_MISMATCH_FAILURE = ExpectedFailure(
    description="streamer TCP against a UDP viewer reports the mismatch",
    streamer_pattern=r"Cannot establish TCP connection .* is the remote side configured for TCP\?",
)

UDP_INTO_TCP_FAILURE = ExpectedFailure(
    description="streamer UDP against a TCP viewer never connects",
)

WRONG_ID_FAILURE = ExpectedFailure(
    description="an unknown relay session ID is rejected on both sides",
    streamer_pattern=r"Unauthorized access - check 'Relay session ID' setting",
    streamer_source=LogSource.SERVICE_MANAGER,
    viewer_pattern=r"Relay setup failed: Peer registration failed",
)

VIEWER_WRONG_ID_FAILURE = ExpectedFailure(
    description="the relay rejects an unknown session ID",
    viewer_pattern=r"Relay setup failed: Peer registration failed",
)


def _viewer_case(name: str, mode: ConnectionMode, transport: Transport, **extra: object) -> TestCase:
    return TestCase(
        name=name,
        phase=Phase.VIEWER,
        mode=mode,
        streamer_transport=transport,
        viewer_transport=transport,
        requires_streamer=False,
        **extra,  # type: ignore[arg-type]
    )


VIEWER_CASES: tuple[TestCase, ...] = (
    _viewer_case("V0-bootstrap", ConnectionMode.DIRECT, Transport.UDP, bootstrap_without_config=True),
    _viewer_case("V1-viewer-direct-tcp", ConnectionMode.DIRECT, Transport.TCP),
    _viewer_case("V2-viewer-relay-udp", ConnectionMode.RELAY, Transport.UDP),
    _viewer_case("V3-viewer-relay-tcp", ConnectionMode.RELAY, Transport.TCP),
)

VIEWER_NEGATIVE_CASES: tuple[TestCase, ...] = (
    _viewer_case(
        "V4-viewer-relay-wrong-id",
        ConnectionMode.RELAY,
        Transport.UDP,
        wrong_relay_id=True,
        expected_failure=VIEWER_WRONG_ID_FAILURE,
    ),
)

LOCAL_CASES: tuple[TestCase, ...] = (
    TestCase(
        name="L1-direct-udp-udp",
        phase=Phase.LOCAL,
        mode=ConnectionMode.DIRECT,
        streamer_transport=Transport.UDP,
        viewer_transport=Transport.UDP,
        with_input_scenario=True,
        with_fault_injection=True,
    ),
    TestCase(
        name="L2-direct-tcp-tcp",
        phase=Phase.LOCAL,
        mode=ConnectionMode.DIRECT,
        streamer_transport=Transport.TCP,
        viewer_transport=Transport.TCP,
    ),
)

LOCAL_NEGATIVE_CASES: tuple[TestCase, ...] = (
    TestCase(
        name="L3-direct-tcp-udp-mismatch",
        phase=Phase.LOCAL,
        mode=ConnectionMode.DIRECT,
        streamer_transport=Transport.TCP,
        viewer_transport=Transport.UDP,
        expected_failure=TCP_MISMATCH_FAILURE,
    ),
    TestCase(
        name="L4-direct-udp-tcp-mismatch",
        phase=Phase.LOCAL,
        mode=ConnectionMode.DIRECT,
        streamer_transport=Transport.UDP,
        viewer_transport=Transport.TCP,
        expected_failure=UDP_INTO_TCP_FAILURE,
    ),
)

RELAY_CASES: tuple[TestCase, ...] = tuple(
    TestCase(
        name=f"R{index}-relay-{streamer}-{viewer}",
        phase=Phase.RELAY,
        mode=ConnectionMode.RELAY,
        streamer_transport=streamer,
        viewer_transport=viewer,
    )
    for index, (streamer, viewer) in enumerate(
        [
            (Transport.UDP, Transport.UDP),
            (Transport.TCP, Transport.TCP),
            (Transport.UDP, Transport.TCP),
            (Transport.TCP, Transport.UDP),
        ],
        start=1,
    )
)

SPECTATOR_CASES: tuple[TestCase, ...] = tuple(
    TestCase(
        name=f"R{index}-relay-{transport}-spectator",
        phase=Phase.RELAY,
        mode=ConnectionMode.RELAY,
        streamer_transport=transport,
        viewer_transport=transport,
        with_spectator=True,
    )
    for index, transport in enumerate([Transport.UDP, Transport.TCP], start=6)
)

SPECTATOR_CASES = (
    *SPECTATOR_CASES,
    TestCase(
        name="R8-relay-udp-spectator-after-viewer",
        phase=Phase.RELAY,
        mode=ConnectionMode.RELAY,
        streamer_transport=Transport.UDP,
        viewer_transport=Transport.UDP,
        with_spectator=True,
        spectator_replaces_viewer=True,
    ),
    TestCase(
        name="R9-relay-udp-viewer-leaves-spectator",
        phase=Phase.RELAY,
        mode=ConnectionMode.RELAY,
        streamer_transport=Transport.UDP,
        viewer_transport=Transport.UDP,
        with_spectator=True,
        viewer_leaves_after_spectator=True,
    ),
    TestCase(
        name="R10-relay-tcp-spectator-after-viewer",
        phase=Phase.RELAY,
        mode=ConnectionMode.RELAY,
        streamer_transport=Transport.TCP,
        viewer_transport=Transport.TCP,
        with_spectator=True,
        spectator_replaces_viewer=True,
    ),
)

RELAY_NEGATIVE_CASES: tuple[TestCase, ...] = (
    TestCase(
        name="R5-relay-wrong-id",
        phase=Phase.RELAY,
        mode=ConnectionMode.RELAY,
        streamer_transport=Transport.UDP,
        viewer_transport=Transport.UDP,
        wrong_relay_id=True,
        expected_failure=WRONG_ID_FAILURE,
    ),
)

STREAMER_PHASES: frozenset[Phase] = frozenset({Phase.LOCAL, Phase.RELAY})


def build_matrix(
    phases: set[Phase], include_negative: bool, with_relay: bool = True, with_spectator: bool = False
) -> list[TestCase]:
    """Viewer-only cases first: they need nothing but the viewer and the relay.

    Without a relay session ID the viewer phase still runs its direct-mode
    cases; the relay phase itself is meaningless without one. Spectator cases
    need a spectator ID and run after the plain relay cases.
    """
    cases: list[TestCase] = []

    if Phase.VIEWER in phases:
        cases.extend(VIEWER_CASES)
        if include_negative:
            cases.extend(VIEWER_NEGATIVE_CASES)

    if Phase.LOCAL in phases:
        cases.extend(LOCAL_CASES)
        if include_negative:
            cases.extend(LOCAL_NEGATIVE_CASES)

    if Phase.RELAY in phases:
        cases.extend(RELAY_CASES)
        if with_spectator:
            cases.extend(SPECTATOR_CASES)

        if include_negative:
            cases.extend(RELAY_NEGATIVE_CASES)

    if not with_relay:
        cases = [case for case in cases if case.mode != ConnectionMode.RELAY]

    return cases


def needs_streamer(phases: set[Phase]) -> bool:
    return bool(phases & STREAMER_PHASES)


def uses_relay(cases: list[TestCase]) -> bool:
    return any(case.mode == ConnectionMode.RELAY for case in cases)
