import logging
import select
import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from v3xctrl_control.message import (
    Error,
    Message,
    PeerAnnouncement,
    PeerInfo,
)
from v3xctrl_helper.exceptions import (
  UnauthorizedError,
  PeerRegistrationError,
  PeerRegistrationAborted,
)
from v3xctrl_helper import Address


class Peer:
    SOCKET_TIMEOUT = 1
    ANNOUNCE_INTERVAL = 1

    def __init__(self, server: str, port: int, session_id: str) -> None:
        self.server = server
        self.port = port
        self.session_id = session_id
        self._abort_event = threading.Event()

        self._finalized_event = threading.Event()
        self._finalized_event.set()

        self._heartbeat_thread = None
        self._heartbeat_socket: socket.socket | None = None

    def setup(self, role: str, ports: dict[str, int]) -> dict[str, Address]:
        self._finalized_event.clear()

        sockets: dict[str, socket.socket] = {}
        try:
            for port_type, port in ports.items():
                upper_pt = port_type.upper()
                sock = self._bind_socket(upper_pt, port)
                sockets[port_type] = sock

            peer_info_map = self._register_all(sockets, role)
        finally:
            self._finalize_sockets(sockets)

        return {
            "video": (
                peer_info_map["video"].get_ip(),
                peer_info_map["video"].get_video_port()
            ),
            "control": (
                peer_info_map["control"].get_ip(),
                peer_info_map["control"].get_control_port()
            )
        }

    def abort(self) -> None:
        self._abort_event.set()

        # Stop heartbeat thread if running
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)

        # Close heartbeat socket if it exists
        if self._heartbeat_socket:
            try:
                self._heartbeat_socket.close()
            except Exception as e:
                logging.debug(f"Error closing heartbeat socket: {e}")
            self._heartbeat_socket = None

        self._finalized_event.wait()

    def _flush_socket(self, sock: socket.socket) -> None:
        while select.select([sock], [], [], 0)[0]:
            try:
                sock.recvfrom(65535)
            except (socket.error, OSError):
                break

    def _bind_socket(self, name: str, port: int = 0) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        logging.info(f"Bound {name} socket to {sock.getsockname()}")
        return sock

    def _register_with_relay(
        self,
        sock: socket.socket,
        port_type: str,
        role: str
    ) -> PeerInfo:
        """
        Register with the relay and wait for PeerInfo response.

        The relay may be forwarding traffic from an existing session, so the
        socket buffer can fill up with non-PeerInfo messages. We flush the
        buffer before each announcement and read continuously to find PeerInfo
        among incoming traffic.

        This runs until one of three states occurs:
        1. abort is called externally
        2. PeerInfo is received from the relay
        3. An error is received from the relay
        """
        announcement = PeerAnnouncement(r=role, i=self.session_id, p=port_type)
        sock.settimeout(self.SOCKET_TIMEOUT)
        last_announce = 0.0

        while not self._abort_event.is_set():
            now = time.time()
            if now - last_announce >= self.ANNOUNCE_INTERVAL:
                self._flush_socket(sock)
                sock.sendto(announcement.to_bytes(), (self.server, self.port))
                logging.debug(f"Sent {port_type} announcement to {self.server}:{self.port} from {sock.getsockname()}")
                last_announce = now

            try:
                data, addr = sock.recvfrom(65535)
                if data:
                    try:
                        response = Message.from_bytes(data)

                        if isinstance(response, PeerInfo):
                            logging.info(f"Received PeerInfo for {port_type}: {response}")
                            return response

                        if isinstance(response, Error):
                            error = response.get_error()
                            self._abort_event.set()

                            logging.error(f"Response Error: {error}")
                            raise UnauthorizedError()

                    except ValueError as e:
                        logging.debug(f"Data could not be parsed: {e}")

            except socket.timeout:
                # Implicit sleep through socket timeout
                continue

            except UnauthorizedError:
                # Don't catch UnauthorizedError - let it propagate
                raise

            except Exception as e:
                logging.debug(f"Error during {port_type} registration: {e}")

        raise InterruptedError(f"Registration aborted for {port_type}")

    def _register_all(self, sockets: dict[str, socket.socket], role: str) -> dict[str, PeerInfo]:
        results: dict[str, PeerInfo] = {}
        exceptions: dict[str, Exception] = {}

        with ThreadPoolExecutor(max_workers=len(sockets)) as executor:
            future_to_port = {
                executor.submit(self._register_with_relay, sock, port_type, role): port_type
                for port_type, sock in sockets.items()
            }

            for future in as_completed(future_to_port):
                port_type = future_to_port[future]
                try:
                    peer_info = future.result()
                    results[port_type] = peer_info
                except Exception as e:
                    exceptions[port_type] = e

        if exceptions:
            # Check if all failures were due to abort
            all_aborted = all(
                isinstance(exc, InterruptedError)
                for exc in exceptions.values()
            )
            if all_aborted:
                raise PeerRegistrationAborted()
            raise PeerRegistrationError(exceptions, results)

        return results

    def _finalize_sockets(self, sockets: dict[str, socket.socket]) -> None:
        for sock in sockets.values():
            sock.settimeout(None)
            sock.close()

        self._finalized_event.set()
