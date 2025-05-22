import logging
import socket
import time
import threading

from rpi_4g_streamer.Message import PeerAnnouncement, Message, PeerInfo


class Peer:
    ANNOUNCE_INTERVAL = 1

    def __init__(self, server: str, port: int, session_id: str, register_timeout: int = 30):
        self.server = server
        self.port = port
        self.session_id = session_id
        self.register_timeout = register_timeout

    def bind_socket(self, name: str, port: int = 0) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        logging.info(f"Bound {name} socket to {sock.getsockname()}")

        return sock

    def register_with_relay(self, sock: socket.socket, port_type: str, role: str) -> bool:
        msg = PeerAnnouncement(r=role, i=self.session_id, p=port_type)
        sock.settimeout(1)
        start_time = time.time()

        while time.time() - start_time < self.register_timeout:
            try:
                # Send the registration announcement
                sock.sendto(msg.to_bytes(), (self.server, self.port))
                logging.debug(f"Sent {port_type} announcement to {self.server}:{self.port} from {sock.getsockname()}")

                # Wait for PeerInfo from the relay
                data, _ = sock.recvfrom(1024)
                msg = Message.from_bytes(data)

                if isinstance(msg, PeerInfo):
                    logging.info(f"[Relay] Received PeerInfo for {port_type}: {msg}")
                    return True

            except socket.timeout:
                time.sleep(self.ANNOUNCE_INTERVAL)
            except Exception as e:
                logging.error(f"[Relay] Error during {port_type} registration: {e}")
                return False

        logging.error(f"Timeout waiting for PeerInfo for {port_type}")
        return False

    def register_all(self, sockets: dict[str, socket.socket], role: str) -> bool:
        success = {pt: [False] for pt in sockets.keys()}

        def reg_worker(pt):
            success[pt][0] = self.register_with_relay(sockets[pt], pt, role)

        threads = [threading.Thread(target=reg_worker, args=(pt,)) for pt in sockets]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return all(success[pt][0] for pt in success)

    def setup(self, role: str, ports: dict[str, int]) -> dict[str, socket.socket]:
        sockets = {
            pt: self.bind_socket(pt.upper(), port)
            for pt, port in ports.items()
        }

        self.register_all(sockets, role)
        self.finalize_sockets(sockets)

    def finalize_sockets(self, sockets: dict[str, socket.socket]):
        for sock in sockets.values():
            sock.settimeout(None)
            sock.close()
