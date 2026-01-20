import logging
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from v3xctrl_control import Server
from v3xctrl_control.message import Heartbeat
from v3xctrl_control.State import State
from v3xctrl_helper.exceptions import PeerRegistrationError, PeerRegistrationAborted
from v3xctrl_udp_relay.Peer import Peer

from v3xctrl_ui.network.video.ReceiverPyAV import ReceiverPyAV as VideoReceiver
from v3xctrl_ui.core.Settings import Settings


@dataclass
class RelaySetupResult:
    """Result of relay connection setup."""
    success: bool
    video_address: Optional[Tuple[str, int]] = None
    error_message: Optional[str] = None


@dataclass
class VideoReceiverSetupResult:
    """Result of video receiver setup."""
    success: bool
    video_receiver: Optional[VideoReceiver] = None
    error: Optional[Exception] = None


@dataclass
class ServerSetupResult:
    """Result of control server setup."""
    success: bool
    server: Optional[Server] = None
    error_message: Optional[str] = None


@dataclass
class NetworkSetupResult:
    """Complete result of network setup process."""
    relay_result: Optional[RelaySetupResult] = None
    video_receiver_result: Optional[VideoReceiverSetupResult] = None
    server_result: Optional[ServerSetupResult] = None

    @property
    def has_errors(self) -> bool:
        """Check if any setup step failed."""
        results = [
            self.relay_result,
            self.video_receiver_result,
            self.server_result
        ]
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
        self._peer: Optional[Peer] = None

    def abort(self) -> None:
        """Abort any in-progress relay setup."""
        if self._peer:
            self._peer.abort()

    def orchestrate_setup(
        self,
        relay_config: Optional[Dict[str, Any]],
        handlers: Dict[str, Any],
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
        if relay_config:
            spectator_mode = relay_config.get('spectator_mode', False)
            relay_result = self.setup_relay(
                relay_config['server'],
                relay_config['port'],
                relay_config['id'],
                spectator_mode
            )
            result.relay_result = relay_result

            # Connection attempt to relay aborted or failed, no need to continue
            if not relay_result.success:
                return result

            video_address = relay_result.video_address

        # Step 2: Create keep-alive callback and setup video receiver
        keep_alive_callback = self.create_keep_alive_callback(video_address)
        video_result = self.setup_video_receiver(keep_alive_callback)
        result.video_receiver_result = video_result

        # Step 3: Setup control server
        server_result = self.setup_server(
            handlers.get("messages", []),
            handlers.get("states", []),
            spectator_mode
        )
        result.server_result = server_result

        return result

    # Step 1
    def setup_relay(
        self,
        relay_server: str,
        relay_port: int,
        relay_id: str,
        spectator_mode: bool = False
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
        local_bind_ports = {
            "video": self.video_port,
            "control": self.control_port
        }

        self._peer = Peer(relay_server, relay_port, relay_id)

        try:
            role = "spectator" if spectator_mode else "viewer"
            addresses = self._peer.setup(role, local_bind_ports)
            video_address = addresses["video"]

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

    # Step 2.a
    def create_keep_alive_callback(
        self,
        video_address: Optional[Tuple[str, int]]
    ) -> Callable[[], None]:
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
                        logging.warning(f"Poke {i+1}/{retries} failed: {e}")

            except Exception as e:
                logging.error(f"Failed to poke peer: {e}", exc_info=True)

            finally:
                if sock:
                    sock.close()
                logging.info(f"Sent 'keep alive' to {video_address}")

        return keep_alive

    # Step 2.b
    def setup_video_receiver(
        self,
        keep_alive_callback: Callable[[], None]
    ) -> VideoReceiverSetupResult:
        """
        Setup video receiver.

        Args:
            keep_alive_callback: Callback to invoke when video stream ends/fails

        Returns:
            VideoReceiverSetupResult with receiver instance or error
        """
        try:
            render_ratio = self.settings.get("video", {}).get("render_ratio", 0)
            video_receiver = VideoReceiver(
                self.video_port,
                keep_alive_callback,
                render_ratio=render_ratio
            )
            video_receiver.start()

            return VideoReceiverSetupResult(
                success=True,
                video_receiver=video_receiver
            )

        except Exception as e:
            return VideoReceiverSetupResult(
                success=False,
                error=e
            )

    # Step 3
    def setup_server(
        self,
        message_handlers: List[Tuple[Any, Callable]],
        state_handlers: List[Tuple[Any, Callable]],
        spectator_mode: bool = False
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

            return ServerSetupResult(
                success=True,
                server=server
            )

        except OSError as e:
            error_msg = (
                "Control port already in use"
                if e.errno == 98
                else f"Server error: {str(e)}"
            )

            return ServerSetupResult(
                success=False,
                error_message=error_msg
            )
