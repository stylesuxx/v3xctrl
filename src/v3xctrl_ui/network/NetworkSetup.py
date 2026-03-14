import errno
import logging
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from v3xctrl_control import Server
from v3xctrl_control.message import Heartbeat, PeerAnnouncement
from v3xctrl_control.State import State
from v3xctrl_helper.exceptions import PeerRegistrationAborted, PeerRegistrationError
from v3xctrl_relay.custom_types import PortType
from v3xctrl_relay.Peer import Peer
from v3xctrl_relay.Role import Role
from v3xctrl_tcp import Transport
from v3xctrl_tcp.TcpTunnel import TcpTunnel
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.network.TcpServer import TcpServer
from v3xctrl_ui.network.video.Receiver import Receiver
from v3xctrl_ui.network.VideoPortKeepAlive import VideoPortKeepAlive
from v3xctrl_ui.utils.gstreamer import is_gstreamer_available

# GStreamer receiver is loaded lazily if available
logger = logging.getLogger(__name__)

# Receivers are loaded lazily to avoid hard dependencies on optional backends
_ReceiverGst: type[Receiver] | None = None
_ReceiverPyAV: type[Receiver] | None = None


def _get_gstreamer_receiver() -> type[Receiver] | None:
    """Get the GStreamer receiver class, loading it lazily."""
    global _ReceiverGst
    if _ReceiverGst is None and is_gstreamer_available():
        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        _ReceiverGst = ReceiverGst
    return _ReceiverGst


def _get_pyav_receiver() -> type[Receiver] | None:
    """Get the PyAV receiver class, loading it lazily."""
    global _ReceiverPyAV
    if _ReceiverPyAV is None:
        try:
            from v3xctrl_ui.network.video.ReceiverPyAV import ReceiverPyAV
            _ReceiverPyAV = ReceiverPyAV
        except ImportError:
            pass
    return _ReceiverPyAV


@dataclass
class RelaySetupResult:
    """Result of relay connection setup."""

    success: bool
    video_address: tuple[str, int] | None = None
    error_message: str | None = None


@dataclass
class VideoReceiverSetupResult:
    """Result of video receiver setup."""

    success: bool
    video_receiver: Receiver | None = None
    error: Exception | None = None


@dataclass
class ServerSetupResult:
    """Result of control server setup."""

    success: bool
    server: Server | None = None
    error_message: str | None = None


@dataclass
class NetworkSetupResult:
    """Complete result of network setup process."""

    relay_result: RelaySetupResult | None = None
    video_receiver_result: VideoReceiverSetupResult | None = None
    server_result: ServerSetupResult | None = None
    video_keep_alive: VideoPortKeepAlive | None = None
    tcp_server: TcpServer | None = None
    tcp_video_tunnel: TcpTunnel | None = None
    tcp_control_tunnel: TcpTunnel | None = None

    @property
    def has_errors(self) -> bool:
        """Check if any setup step failed."""
        results = [self.relay_result, self.video_receiver_result, self.server_result]
        return any(r and not r.success for r in results)


class NetworkSetup:
    """Orchestrates network component setup with clear error handling.

    This happens in three steps
    1. Relay setup (optional): If relay is enabled, this established connection
       to the relay. This blocks until one of the following conditions is met
       * Relay replies with PeerInfo
       * Peer announcement is aborted (for example by switching to direct mode)
       * Peer registration fails (for example because of wrong session/spectator
         ID)
    2. Video receiver setup: This step is triggered in any case, no matter if
       direct or relay connection. Video receiver is started in the background
       and runs in a separate thread.
    3. Control channel setup: This step is also triggered in both cases and sets
       up the bi-directional control channel for sending control and receiving
       telemetry. Runs in a separate thread like the video receiver
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.ports = settings.get("ports", {})
        self.video_port = self.ports.get("video")
        self.control_port = self.ports.get("control")
        self.transport = settings.get("transport", Transport.UDP)
        self._peer: Peer | None = None

    def abort(self) -> None:
        """Abort any in-progress relay setup."""
        if self._peer:
            self._peer.abort()

    def orchestrate_setup(
        self,
        relay_config: dict[str, Any] | None,
        handlers: dict[str, Any],
    ) -> NetworkSetupResult:
        """
        Orchestrate complete network setup.

        Args:
            relay_config: Optional relay configuration with keys:
                         'server', 'port', 'id'. If None, no relay used.
            handlers: Dictionary with 'messages' and 'states' handler lists

        Returns:
            NetworkSetupResult with all setup results
        """
        result = NetworkSetupResult()

        # Step 1: Setup relay if configured
        video_address = None
        spectator_mode = False

        if self.transport == Transport.TCP and relay_config:
            # TCP relay mode: two TcpTunnels to relay, skip Peer.setup()
            relay_host = relay_config["server"]
            relay_port = relay_config["port"]
            session_id = relay_config["id"]
            spectator_mode = relay_config.get("spectator_mode", False)
            role = Role.SPECTATOR if spectator_mode else Role.VIEWER

            video_handshake = PeerAnnouncement(r=role.value, i=session_id, p=PortType.VIDEO.value).to_bytes()
            result.tcp_video_tunnel = TcpTunnel(
                remote_host=relay_host,
                remote_port=relay_port,
                local_component_port=self.video_port,
                bidirectional=True,
                handshake=video_handshake,
            )
            result.tcp_video_tunnel.start()

            control_handshake = PeerAnnouncement(r=role.value, i=session_id, p=PortType.CONTROL.value).to_bytes()
            result.tcp_control_tunnel = TcpTunnel(
                remote_host=relay_host,
                remote_port=relay_port,
                local_component_port=self.control_port,
                bidirectional=True,
                handshake=control_handshake,
            )
            result.tcp_control_tunnel.start()

            logger.info("TCP relay tunnels started (video + control)")

        elif relay_config:
            spectator_mode = relay_config.get("spectator_mode", False)
            relay_result = self.setup_relay(
                relay_config["server"], relay_config["port"], relay_config["id"], spectator_mode
            )
            result.relay_result = relay_result

            # Connection attempt to relay aborted or failed, no need to continue
            if not relay_result.success:
                return result

            video_address = relay_result.video_address

        # Start periodic video port keep-alive for relay connections
        if video_address:
            keep_alive_thread = VideoPortKeepAlive(
                video_port=self.video_port,
                relay_host=video_address[0],
                relay_port=video_address[1],
            )
            keep_alive_thread.start()
            result.video_keep_alive = keep_alive_thread

        elif self.transport == Transport.TCP and not relay_config:
            # Start TCP server for direct TCP mode
            result.tcp_server = TcpServer(self.video_port, self.control_port)
            result.tcp_server.start()
            logger.info("TCP server started for direct mode")

        # Step 2: Create keep-alive callback and setup video receiver
        keep_alive_callback = self.create_keep_alive_callback(video_address)
        video_result = self.setup_video_receiver(keep_alive_callback, video_address)
        result.video_receiver_result = video_result

        # Step 3: Setup control server
        server_result = self.setup_server(handlers.get("messages", []), handlers.get("states", []), spectator_mode)
        result.server_result = server_result

        return result

    # Step 1
    def setup_relay(
        self, relay_server: str, relay_port: int, relay_id: str, spectator_mode: bool = False
    ) -> RelaySetupResult:
        """
        Setup relay connection.

        Args:
            relay_server: Relay server hostname
            relay_port: Relay server port
            relay_id: Session ID for relay
            spectator_mode: Whether to register as spectator instead of viewer

        Returns:
            RelaySetupResult with connection details or error
        """
        local_bind_ports = {PortType.VIDEO.value: self.video_port, PortType.CONTROL.value: self.control_port}

        self._peer = Peer(relay_server, relay_port, relay_id)

        try:
            role = Role.SPECTATOR if spectator_mode else Role.VIEWER
            addresses = self._peer.setup(role.value, local_bind_ports)
            video_address = addresses.video

            return RelaySetupResult(
                success=True,
                video_address=video_address,
            )

        except PeerRegistrationAborted:
            return RelaySetupResult(
                success=False,
                error_message="Registration aborted",
            )

        except PeerRegistrationError:
            return RelaySetupResult(
                success=False,
                error_message="Peer registration failed - check server and ID!",
            )

        except OSError as e:
            error_msg = "Port already in use" if e.errno == errno.EADDRINUSE else "Network error"
            return RelaySetupResult(
                success=False,
                error_message=error_msg,
            )

    # Step 2.a
    def create_keep_alive_callback(self, video_address: tuple[str, int] | None) -> Callable[[], None]:
        """
        Create a keep-alive callback for relay connections.

        This opens a new socket on the video port, so there must not be a socket
        running on this port. Make sure to only call this function when PyAV or
        whichever video receiver is in use does not have a socket connection
        open.

        Args:
            video_address: Remote video address to send keep-alive packets to

        Returns:
            Callable that sends keep-alive packets to video port
        """
        if not video_address:
            return lambda: None

        def keep_alive() -> None:
            retries = 3
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", self.video_port))

                for i in range(retries):
                    try:
                        sock.sendto(Heartbeat().to_bytes(), video_address)
                        time.sleep(0.1)
                    except Exception as e:
                        logger.warning(f"Poke {i + 1}/{retries} failed: {e}")

            except Exception as e:
                logger.error(f"Failed to poke peer: {e}", exc_info=True)

            finally:
                if sock:
                    sock.close()
                logger.info(f"Sent 'keep alive' to {video_address}")

        return keep_alive

    # Step 2.b
    def setup_video_receiver(
        self,
        keep_alive_callback: Callable[[], None],
        video_address: tuple[str, int] | None = None,
    ) -> VideoReceiverSetupResult:
        """
        Setup video receiver.

        Args:
            keep_alive_callback: Callback to invoke when video stream ends/fails
            video_address: Relay video address for NAT keepalive

        Returns:
            VideoReceiverSetupResult with receiver instance or error
        """
        video_settings = self.settings.get("video", {})
        render_ratio = video_settings.get("render_ratio", 0)
        receiver_type = video_settings.get("receiver", "auto")

        try:
            match receiver_type:
                case "auto":
                    gst_receiver = _get_gstreamer_receiver()
                    pyav_receiver = _get_pyav_receiver()
                    if gst_receiver:
                        video_receiver: Receiver = gst_receiver(
                            self.video_port,
                            keep_alive_callback,
                            render_ratio=render_ratio,
                        )
                        receiver_type = "gst"
                    elif pyav_receiver:
                        video_receiver = pyav_receiver(
                            self.video_port,
                            keep_alive_callback,
                            render_ratio=render_ratio,
                            relay_address=video_address,
                        )
                        receiver_type = "pyav"
                    else:
                        raise RuntimeError("No video receiver available (neither GStreamer nor PyAV found)")
                case "gst":
                    gst_receiver = _get_gstreamer_receiver()
                    if not gst_receiver:
                        raise RuntimeError("GStreamer receiver requested but not available")
                    video_receiver = gst_receiver(
                        self.video_port,
                        keep_alive_callback,
                        render_ratio=render_ratio,
                    )
                case "pyav":
                    pyav_receiver = _get_pyav_receiver()
                    if not pyav_receiver:
                        raise RuntimeError("PyAV receiver requested but not available")
                    video_receiver = pyav_receiver(
                        self.video_port,
                        keep_alive_callback,
                        render_ratio=render_ratio,
                        relay_address=video_address,
                    )
                case _:
                    raise ValueError(f"Unknown receiver type: {receiver_type}")

            logger.info(f"Using {receiver_type} video receiver")

            # Enable timing when DEBUG level is set
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                video_receiver.enable_timing(True)

            video_receiver.start()

            return VideoReceiverSetupResult(success=True, video_receiver=video_receiver)

        except Exception as e:
            return VideoReceiverSetupResult(success=False, error=e)

    # Step 3
    def setup_server(
        self,
        message_handlers: list[tuple[Any, Callable]],
        state_handlers: list[tuple[Any, Callable]],
        spectator_mode: bool = False,
    ) -> ServerSetupResult:
        """
        Setup control server.

        Args:
            message_handlers: List of (message_type, callback) tuples
            state_handlers: List of (state, callback) tuples
            spectator_mode: Whether to start in spectating state

        Returns:
            ServerSetupResult with server instance or error message
        """
        try:
            udp_ttl_ms = self.settings.get("udp_packet_ttl", 100)
            server = Server(self.control_port, udp_ttl_ms)

            for message_type, callback in message_handlers:
                server.subscribe(message_type, callback)

            for state, callback in state_handlers:
                server.on(state, callback)

            # Set initial state based on spectator mode
            if spectator_mode:
                server.state = State.SPECTATING

            server.start()

            return ServerSetupResult(success=True, server=server)

        except OSError as e:
            error_msg = "Control port already in use" if e.errno == errno.EADDRINUSE else "Server error"

            return ServerSetupResult(success=False, error_message=error_msg)
