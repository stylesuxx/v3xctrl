import logging
import socket
import time
import threading

from rpi_4g_streamer.Message import (
    Message, PeerAnnouncement, PeerInfo,
    Syn, SynAck, Ack
)


class AckTimeoutError(Exception):
    """Raised when Ack is not received within the expected time window."""
    pass


class PunchPeer:
    ANNOUNCE_INTERVAL = 5

    def __init__(self, server, port, session_id, register_timeout: int = 300):
        self.server = server
        self.port = port
        self.session_id = session_id
        self.register_timeout = register_timeout

    def bind_socket(self, name, port=0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        logging.info(f"Bound {name} socket to {sock.getsockname()}")

        return sock

    def register_with_rendezvous(self, sock, announcement_msg):
        assert isinstance(announcement_msg, PeerAnnouncement)
        sock.settimeout(1)
        start_time = time.time()

        while time.time() - start_time < self.register_timeout:
            try:
                sock.sendto(announcement_msg.to_bytes(), (self.server, self.port))
                logging.info(f"Sent {announcement_msg.type} from port {sock.getsockname()[1]} to {self.server}:{self.port}")

                data, _ = sock.recvfrom(1024)
                peer_msg = Message.from_bytes(data)

                if isinstance(peer_msg, PeerInfo):
                    logging.info(f"Got peer info: {peer_msg}")
                    return peer_msg
                else:
                    logging.debug(f"Unexpected message type: {peer_msg.type}")

            except socket.timeout:
                time.sleep(self.ANNOUNCE_INTERVAL)
            except Exception as e:
                logging.error(f"Registration error: {e}")
                return None

        logging.error(f"Timeout registering: {announcement_msg}")
        return None

    def register_all(self, sockets: dict[str, socket.socket], role: str) -> dict[str, PeerInfo]:
        results = {pt: [None] for pt in sockets.keys()}

        def reg_worker(pt):
            ann = PeerAnnouncement(r=role, i=self.session_id, p=pt)
            results[pt][0] = self.register_with_rendezvous(sockets[pt], ann)

        threads = [threading.Thread(target=reg_worker, args=(pt,)) for pt in sockets]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return {pt: results[pt][0] for pt in results}

    def _handshake(self, sock: socket.socket, addr: tuple, interval=0.5, timeout=10.0):
        logging.info(f"Starting Syn loop to {addr}")
        sock.settimeout(interval)
        start_time = time.time()
        received_synack = False
        sent_ack = False

        while time.time() - start_time < timeout:
            try:
                sock.sendto(Syn().to_bytes(), addr)
                logging.info(f"Sent Syn to {addr}")

                data, source = sock.recvfrom(1024)
                msg = Message.from_bytes(data)

                if isinstance(msg, Syn):
                    sock.sendto(SynAck().to_bytes(), source)
                    logging.info(f"Replied with SynAck to Syn from {source}")

                elif isinstance(msg, SynAck):
                    logging.info(f"Received SynAck from {source}")
                    sock.sendto(Ack().to_bytes(), source)
                    logging.info(f"Sent Ack to {source}")
                    received_synack = True
                    sent_ack = True

                elif isinstance(msg, Ack):
                    logging.info(f"Received final Ack from {source}")
                    return True

                if received_synack and sent_ack:
                    return True

            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"[!] Handshake error: {e}")
                continue

            time.sleep(interval)

        raise AckTimeoutError(f"No Ack received from {addr} after {timeout:.1f}s")

    def rendezvous_and_punch(self, role: str, sockets: dict[str, socket.socket]) -> dict[str, PeerInfo]:
        peer_info = self.register_all(sockets, role=role)
        if not all(isinstance(p, PeerInfo) for p in peer_info.values()):
            raise RuntimeError("Registration failed or incomplete")

        peer = peer_info["video"]
        ip = peer.get_ip()
        video_port = peer.get_video_port()
        control_port = peer.get_control_port()

        threads = [
            threading.Thread(target=self._handshake, args=(sockets["video"], (ip, video_port))),
            threading.Thread(target=self._handshake, args=(sockets["control"], (ip, control_port)))
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return peer_info

    def finalize_sockets(self, sockets: dict[str, socket.socket]):
        for sock in sockets.values():
            sock.settimeout(None)
            #sock.close()

    def setup(self, role: str, ports: dict[str, int]) -> dict[str, PeerInfo]:
        sockets = {
            pt: self.bind_socket(pt.upper(), port)
            for pt, port in ports.items()
        }
        peer_info = self.rendezvous_and_punch(role, sockets)
        self.finalize_sockets(sockets)
        return (sockets, peer_info)
