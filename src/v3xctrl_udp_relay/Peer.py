import logging
import socket
import time
import threading
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from v3xctrl_control.message import PeerAnnouncement, Message, PeerInfo, Error
from v3xctrl_helper.exceptions import UnauthorizedError
from v3xctrl_helper import Address


class PeerRegistrationError(Exception):
    def __init__(self, failures: Dict[str, Exception], successes: Dict[str, PeerInfo]):
        self.failures = failures
        self.successes = successes
        failed_ports = list(failures.keys())
        super().__init__(f"Registration failed for ports: {failed_ports}")


class Peer:
    SOCKET_TIMEOUT = 1
    ANNOUNCE_INTERVAL = 1
    MAX_READ_COUNT = 3

    def __init__(self, server: str, port: int, session_id: str) -> None:
        self.server = server
        self.port = port
        self.session_id = session_id
        self._abort_event = threading.Event()

    def setup(self, role: str, ports: Dict[str, int]) -> Dict[str, Address]:
        sockets: Dict[str, socket.socket] = {}
        for port_type, port in ports.items():
            upper_pt = port_type.upper()
            sock = self._bind_socket(upper_pt, port)
            sockets[port_type] = sock

        try:
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
        When re-connecting we need to catch the PeerInfo.

        The relay is still forwarding video and control messages though, so we
        need to make sure we don't fail when we get one of those during setup.

        To comensate for this, we attempt to read a couple of times after
        sending the initial request, this gives us a chance to catch the
        PeerInfo message somewhere in-between.

        This runs until one of three states occurs:
        1. abort is called externally
        2. PeerInfo is received from the relay
        3. An error is received from the relay
        """
        announcement = PeerAnnouncement(r=role, i=self.session_id, p=port_type)
        sock.settimeout(self.SOCKET_TIMEOUT)

        while not self._abort_event.is_set():
            try:
                sock.sendto(announcement.to_bytes(), (self.server, self.port))
                logging.debug(f"Sent {port_type} announcement to {self.server}:{self.port} from {sock.getsockname()}")

                read_count = 0
                while read_count < self.MAX_READ_COUNT:
                    data, _ = sock.recvfrom(1024)
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

                    read_count += 1

            except socket.timeout:
                # Implicit sleep through socket timeout
                continue

            except UnauthorizedError:
                # Don't catch UnauthorizedError - let it propagate
                raise

            except Exception as e:
                logging.debug(f"Error during {port_type} registration: {e}")

            # Sleep a bit before trying again
            time.sleep(self.ANNOUNCE_INTERVAL)
            continue

        # If we reach here, registration was aborted
        raise InterruptedError(f"Registration aborted for {port_type}")

    def _register_all(self, sockets: Dict[str, socket.socket], role: str) -> Dict[str, PeerInfo]:
        results: Dict[str, PeerInfo] = {}
        exceptions: Dict[str, Exception] = {}

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
            raise PeerRegistrationError(exceptions, results)

        return results

    def _finalize_sockets(self, sockets: Dict[str, socket.socket]) -> None:
        for sock in sockets.values():
            sock.settimeout(None)
            sock.close()
