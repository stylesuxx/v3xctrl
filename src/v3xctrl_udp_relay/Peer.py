import logging
import socket
import time
import threading
from typing import Dict, List, Any

from v3xctrl_control.message import PeerAnnouncement, Message, PeerInfo, Error
from v3xctrl_helper.exceptions import UnauthorizedError
from v3xctrl_helper import Address


class Peer:
    ANNOUNCE_INTERVAL = 1

    def __init__(self, server: str, port: int, session_id: str) -> None:
        self.server = server
        self.port = port
        self.session_id = session_id
        self._abort_event = threading.Event()

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
    ) -> PeerInfo | None:
        announcement = PeerAnnouncement(r=role, i=self.session_id, p=port_type)
        sock.settimeout(1)

        while not self._abort_event.is_set():
            data = None
            try:
                sock.sendto(announcement.to_bytes(), (self.server, self.port))
                logging.debug(f"Sent {port_type} announcement to {self.server}:{self.port} from {sock.getsockname()}")

                data, _ = sock.recvfrom(1024)

            except socket.timeout:
                time.sleep(self.ANNOUNCE_INTERVAL)
                continue
            except Exception as e:
                logging.debug(f"[Relay] Error during {port_type} registration: {e}")
                continue

            if data:
                response = Message.from_bytes(data)

                if isinstance(response, PeerInfo):
                    logging.info(f"[Relay] Received PeerInfo for {port_type}: {response}")
                    return response

                if isinstance(response, Error):
                    error = response.get_error()
                    self._abort_event.set()

                    logging.error(f"Response Error: {error}")
                    raise UnauthorizedError()

    def _register_all(
        self,
        sockets: Dict[str, socket.socket],
        role: str
    ) -> Dict[str, PeerInfo]:
        results: Dict[str, Any] = {port_type: [None] for port_type in sockets.keys()}
        exceptions: List[Exception] = []

        def reg_worker(port_type: str) -> None:
            try:
                results[port_type][0] = self._register_with_relay(sockets[port_type], port_type, role)
            except Exception as e:
                exceptions.append(e)

        threads = [threading.Thread(target=reg_worker, args=(pt,)) for pt in sockets]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if exceptions:
            raise exceptions[0]  # Or raise a custom aggregate error if needed

        return {pt: results[pt][0] for pt in results}

    def _finalize_sockets(self, sockets: Dict[str, socket.socket]) -> None:
        for sock in sockets.values():
            sock.settimeout(None)
            sock.close()

    def setup(self, role: str, ports: Dict[str, int]) -> Dict[str, Address]:
        sockets: Dict[str, socket.socket] = {}
        for port_type, port in ports.items():
            upper_pt = port_type.upper()
            sock = self._bind_socket(upper_pt, port)
            sockets[port_type] = sock

        peer_info_map = self._register_all(sockets, role)
        self._finalize_sockets(sockets)

        address_map = {
            "video": (peer_info_map["video"].get_ip(), peer_info_map["video"].get_video_port()),
            "control": (peer_info_map["control"].get_ip(), peer_info_map["control"].get_control_port())
        }

        return address_map

    def abort(self) -> None:
        self._abort_event.set()
