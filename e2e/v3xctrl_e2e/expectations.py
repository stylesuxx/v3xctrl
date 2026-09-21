"""Which log lines each test case must and must not produce."""

from dataclasses import dataclass, field

from v3xctrl_e2e.log_expectations import Forbidden, LogSource, Required
from v3xctrl_e2e.matrix import ConnectionMode, TestCase
from v3xctrl_tcp.transport import Transport

VIEWER_RECEIVER_CHOSEN = Required("GStreamer receiver chosen", LogSource.VIEWER, r"Using gst video receiver")
VIEWER_RECEIVER_STARTED = Required("receiver started", LogSource.VIEWER, r"GStreamer receiver started on port")
VIEWER_PIPELINE_PLAYING = Required("video pipeline playing", LogSource.VIEWER, r"Pipeline is now PLAYING")
VIEWER_CONTROL_CONNECTED = Required("control channel connected", LogSource.VIEWER, r"Control channel connected")
VIEWER_FIRST_TELEMETRY = Required("first telemetry", LogSource.VIEWER, r"First telemetry message received")
VIEWER_GAMEPAD_DETECTED = Required("gamepad detected", LogSource.VIEWER, r"New gamepad detected")
VIEWER_GAMEPAD_ACTIVE = Required("gamepad activated", LogSource.VIEWER, r"Found default gamepad")

VIEWER_RELAY_UDP = [
    Required("relay video registration", LogSource.VIEWER, r"Received PeerInfo for video:"),
    Required("relay control registration", LogSource.VIEWER, r"Received PeerInfo for control:"),
]
VIEWER_RELAY_TCP = [
    Required("relay TCP tunnels", LogSource.VIEWER, r"TCP relay tunnels started \(video \+ control\)"),
    Required("relay TCP handshakes", LogSource.VIEWER, r"TcpTunnel handshake complete", minimum_count=2),
]
VIEWER_DIRECT_TCP = [
    Required("direct TCP servers", LogSource.VIEWER, r"TCP server listening on port", minimum_count=2),
    Required("direct TCP clients", LogSource.VIEWER, r"TCP client connected on port", minimum_count=2),
]

STREAMER_PIPELINE_BUILT = Required("streamer pipeline built", LogSource.VIDEO, r"Building pipeline\.\.\.")
STREAMER_CONTROL_CONNECTED = Required("streamer control connected", LogSource.CONTROL, r" - Connected$")
STREAMER_RELAY_UDP = [
    Required("streamer relay video registration", LogSource.SERVICE_MANAGER, r"Received PeerInfo for video:"),
    Required("streamer relay control registration", LogSource.SERVICE_MANAGER, r"Received PeerInfo for control:"),
]
STREAMER_TCP_TUNNELS = [
    Required("streamer video tunnel", LogSource.VIDEO, r"TcpTunnel connected to"),
    Required("streamer control tunnel", LogSource.CONTROL, r"TcpTunnel connected to"),
]
STREAMER_TCP_RELAY_HANDSHAKES = [
    Required("streamer video relay handshake", LogSource.VIDEO, r"TcpTunnel handshake complete"),
    Required("streamer control relay handshake", LogSource.CONTROL, r"TcpTunnel handshake complete"),
]

STREAMER_ALLOWED_WARNINGS: tuple[str, ...] = (
    r"Failed to initialize modem",
    r"GPS: no UBX",
    r"GPS: detecting baud",
)

VIEWER_FORBIDDEN = [
    Forbidden("viewer traceback", LogSource.VIEWER, r"Traceback"),
    Forbidden("viewer GStreamer error", LogSource.VIEWER, r"GStreamer error:"),
    Forbidden("viewer bind failure", LogSource.VIEWER, r"Failed to bind"),
    Forbidden("viewer port in use", LogSource.VIEWER, r"Port already in use"),
    Forbidden("viewer relay registration failure", LogSource.VIEWER, r"Peer registration failed"),
    Forbidden("viewer PyAV fallback", LogSource.VIEWER, r"Using pyav video receiver"),
]

STREAMER_FORBIDDEN = [
    Forbidden("streamer traceback", LogSource.VIDEO, r"Traceback"),
    Forbidden("streamer traceback", LogSource.CONTROL, r"Traceback"),
    Forbidden("streamer pipeline failure", LogSource.VIDEO, r"Failed to build pipeline"),
    Forbidden("streamer pipeline failure", LogSource.VIDEO, r"Unable to set the pipeline to the playing state"),
    Forbidden("streamer relay rejection", LogSource.SERVICE_MANAGER, r"Unauthorized access"),
    Forbidden("streamer control error", LogSource.CONTROL, r" - ERROR - ", allowed=STREAMER_ALLOWED_WARNINGS),
]

VIEWER_RELAY_UDP_ANNOUNCING = [
    Required("relay sockets bound", LogSource.VIEWER, r"Bound \w+ socket to", minimum_count=2),
    Required("video announcement sent", LogSource.VIEWER, r"Sent video announcement to"),
    Required("control announcement sent", LogSource.VIEWER, r"Sent control announcement to"),
]
VIEWER_RELAY_TCP_STARTED = [
    Required("relay TCP tunnels", LogSource.VIEWER, r"TCP relay tunnels started \(video \+ control\)"),
    Required(
        "relay TCP proxies bound", LogSource.VIEWER, r"TcpTunnel UDP proxy bound on ephemeral port", minimum_count=2
    ),
]
VIEWER_DIRECT_TCP_LISTENING = [
    Required("direct TCP servers", LogSource.VIEWER, r"TCP server listening on port", minimum_count=2),
]

VIEWER_RELAY_FORBIDDEN = [
    Forbidden("viewer relay setup failure", LogSource.VIEWER, r"Relay setup failed"),
    Forbidden("relay rejected the viewer", LogSource.VIEWER, r"Response Error"),
    Forbidden("viewer relay TCP unreachable", LogSource.VIEWER, r"Cannot establish TCP connection"),
    Forbidden("viewer relay TCP connect attempt failed", LogSource.VIEWER, r"TCP connect failed"),
]

STEADY_FORBIDDEN = [
    Forbidden("control dropped during steady window", LogSource.VIEWER, r"Control channel disconnected"),
    Forbidden("control timeout during steady window", LogSource.VIEWER, r"No message received for"),
    Forbidden("video gap during steady window", LogSource.VIEWER, r"No frames received for"),
    Forbidden("streamer control dropped during steady window", LogSource.CONTROL, r" - Disconnected$"),
    Forbidden("streamer failsafe during steady window", LogSource.CONTROL, r"No message received for"),
]


@dataclass(frozen=True)
class Expectations:
    """`connection` is polled until met; `run` is checked once at the end.

    `spectator_connection` is polled for the second viewer once the first one
    is connected; its forbidden rules join `forbidden` and `steady_forbidden`.
    """

    connection: list[Required]
    run: list[Required]
    forbidden: list[Forbidden]
    steady_forbidden: list[Forbidden]
    spectator_connection: list[Required] = field(default_factory=list)


SPECTATOR_FORBIDDEN = [
    Forbidden("spectator traceback", LogSource.SPECTATOR, r"Traceback"),
    Forbidden("spectator GStreamer error", LogSource.SPECTATOR, r"GStreamer error:"),
    Forbidden("spectator relay setup failure", LogSource.SPECTATOR, r"Relay setup failed"),
    Forbidden("relay rejected the spectator", LogSource.SPECTATOR, r"Response Error"),
    Forbidden("spectator PyAV fallback", LogSource.SPECTATOR, r"Using pyav video receiver"),
]

SPECTATOR_STEADY_FORBIDDEN = [
    Forbidden("spectator video gap during steady window", LogSource.SPECTATOR, r"No frames received for"),
    Forbidden("spectator relay tunnel dropped during steady window", LogSource.SPECTATOR, r"TcpTunnel disconnected"),
]


def spectator_connection_for(test_case: TestCase) -> list[Required]:
    connection = [
        Required("spectator GStreamer receiver chosen", LogSource.SPECTATOR, r"Using gst video receiver"),
        Required("spectator video pipeline playing", LogSource.SPECTATOR, r"Pipeline is now PLAYING"),
    ]
    if test_case.viewer_transport == Transport.UDP:
        connection.extend(
            [
                Required("spectator relay video registration", LogSource.SPECTATOR, r"Received PeerInfo for video:"),
                Required(
                    "spectator relay control registration", LogSource.SPECTATOR, r"Received PeerInfo for control:"
                ),
            ]
        )
    else:
        connection.extend(
            [
                Required("spectator relay TCP tunnels", LogSource.SPECTATOR, r"TCP relay tunnels started"),
                Required(
                    "spectator relay TCP handshakes",
                    LogSource.SPECTATOR,
                    r"TcpTunnel handshake complete",
                    minimum_count=2,
                ),
            ]
        )
    return connection


def expectations_for(test_case: TestCase, with_gamepad: bool) -> Expectations:
    if not test_case.is_expected_to_connect:
        return Expectations(connection=[], run=[], forbidden=[], steady_forbidden=[])

    if not test_case.requires_streamer:
        return viewer_only_expectations_for(test_case)

    connection = [
        VIEWER_RECEIVER_CHOSEN,
        VIEWER_RECEIVER_STARTED,
        VIEWER_PIPELINE_PLAYING,
        VIEWER_CONTROL_CONNECTED,
        VIEWER_FIRST_TELEMETRY,
    ]
    run = [STREAMER_PIPELINE_BUILT, STREAMER_CONTROL_CONNECTED]

    if with_gamepad:
        connection.extend([VIEWER_GAMEPAD_DETECTED, VIEWER_GAMEPAD_ACTIVE])

    match (test_case.mode, test_case.viewer_transport):
        case (ConnectionMode.RELAY, Transport.UDP):
            connection.extend(VIEWER_RELAY_UDP)

        case (ConnectionMode.RELAY, Transport.TCP):
            connection.extend(VIEWER_RELAY_TCP)

        case (ConnectionMode.DIRECT, Transport.TCP):
            connection.extend(VIEWER_DIRECT_TCP)

    match (test_case.mode, test_case.streamer_transport):
        case (ConnectionMode.RELAY, Transport.UDP):
            run.extend(STREAMER_RELAY_UDP)

        case (ConnectionMode.RELAY, Transport.TCP):
            run.extend(STREAMER_TCP_TUNNELS + STREAMER_TCP_RELAY_HANDSHAKES)

        case (ConnectionMode.DIRECT, Transport.TCP):
            run.extend(STREAMER_TCP_TUNNELS)

    forbidden = VIEWER_FORBIDDEN + STREAMER_FORBIDDEN
    steady_forbidden = list(STEADY_FORBIDDEN)
    spectator_connection: list[Required] = []
    if test_case.with_spectator:
        forbidden = forbidden + SPECTATOR_FORBIDDEN
        steady_forbidden.extend(SPECTATOR_STEADY_FORBIDDEN)
        spectator_connection = spectator_connection_for(test_case)

    if test_case.spectator_replaces_viewer:
        # The viewer leaves on purpose, so the streamer losing its control peer
        # is the expected state; only the spectator has to stay healthy.
        forbidden = [rule for rule in forbidden if rule.source != LogSource.CONTROL]
        steady_forbidden = list(SPECTATOR_STEADY_FORBIDDEN)

    if test_case.viewer_leaves_after_spectator:
        # The spectator is meant to lose its video once the viewer is gone, so
        # a video gap is the outcome under test, not a failure.
        forbidden = [rule for rule in forbidden if rule.source != LogSource.CONTROL]
        steady_forbidden = []

    return Expectations(
        connection=connection,
        run=run,
        forbidden=forbidden,
        steady_forbidden=steady_forbidden,
        spectator_connection=spectator_connection,
    )


def viewer_only_expectations_for(test_case: TestCase) -> Expectations:
    """What a viewer proves on its own: it comes up, binds, and reaches the relay.

    The relay answers a registration only once both peers are present. Over UDP
    that blocks the rest of the setup, so the case proves the announcements go
    out. Over TCP the tunnels start and the handshake waits for its response, so
    the case proves the tunnels are up and the TCP connect itself never failed.
    """
    match (test_case.mode, test_case.viewer_transport):
        case (ConnectionMode.RELAY, Transport.UDP):
            connection = list(VIEWER_RELAY_UDP_ANNOUNCING)

        case (ConnectionMode.RELAY, Transport.TCP):
            connection = [VIEWER_RECEIVER_CHOSEN, VIEWER_RECEIVER_STARTED, *VIEWER_RELAY_TCP_STARTED]

        case (ConnectionMode.DIRECT, Transport.TCP):
            connection = [VIEWER_RECEIVER_CHOSEN, VIEWER_RECEIVER_STARTED, *VIEWER_DIRECT_TCP_LISTENING]

        case _:
            connection = [VIEWER_RECEIVER_CHOSEN, VIEWER_RECEIVER_STARTED]

    forbidden = VIEWER_FORBIDDEN + VIEWER_RELAY_FORBIDDEN
    return Expectations(connection=connection, run=[], forbidden=forbidden, steady_forbidden=forbidden)


def failure_expectations_for(test_case: TestCase) -> list[Required]:
    """The lines a negative test waits for."""
    failure = test_case.expected_failure
    if failure is None:
        return []

    required: list[Required] = []
    if failure.streamer_pattern is not None:
        required.append(Required(failure.description, failure.streamer_source, failure.streamer_pattern))

    if failure.viewer_pattern is not None:
        required.append(Required(failure.description, LogSource.VIEWER, failure.viewer_pattern))

    return required
