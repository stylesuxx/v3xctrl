import socket
import time
import threading

from rpi_4g_streamer.Message import Message, PeerAnnouncement, PeerInfo


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
        print(f"[+] Bound {name} socket to {sock.getsockname()}")
        return sock

    def register_with_rendezvous(self, sock, announcement_msg):
        assert isinstance(announcement_msg, PeerAnnouncement)
        sock.settimeout(1)
        start_time = time.time()

        while time.time() - start_time < self.register_timeout:
            try:
                sock.sendto(announcement_msg.to_bytes(), (self.server, self.port))
                print(f"[→] Sent {announcement_msg.type} from port {sock.getsockname()[1]}")

                data, _ = sock.recvfrom(1024)
                peer_msg = Message.from_bytes(data)
                if isinstance(peer_msg, PeerInfo):
                    print(f"[✓] Got peer info: {peer_msg}")
                    return peer_msg
                else:
                    print(f"[!] Unexpected message type: {peer_msg.type}")
            except socket.timeout:
                time.sleep(self.ANNOUNCE_INTERVAL)
            except Exception as e:
                print(f"[!] Registration error: {e}")
                return None

        print(f"[!] Timeout registering: {announcement_msg}")
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

    def send_pokes(self, sock_map: dict[str, socket.socket], peer_info: PeerInfo):
        for _ in range(3):
            sock_map["video"].sendto(b'poke-video', (peer_info.get_ip(), peer_info.get_video_port()))
            sock_map["control"].sendto(b'poke-control', (peer_info.get_ip(), peer_info.get_control_port()))
            time.sleep(0.3)

    def rendezvous_and_punch(self, role: str, sockets: dict[str, socket.socket]) -> tuple[dict[str, socket.socket], dict[str, PeerInfo]]:
        peer_info = self.register_all(sockets, role=role)
        if not all(isinstance(p, PeerInfo) for p in peer_info.values()):
            raise RuntimeError("[!] Registration failed or incomplete")
        self.send_pokes(sockets, peer_info["video"])
        return sockets, peer_info

    def finalize_sockets(self, sockets: dict[str, socket.socket]):
        for sock in sockets.values():
            sock.settimeout(None)

    def setup(self, role: str, ports: dict[str, int]) -> tuple[dict[str, socket.socket], dict[str, PeerInfo]]:
        sockets = {
            pt: self.bind_socket(pt.upper(), port)
            for pt, port in ports.items()
        }
        sockets, peer_info = self.rendezvous_and_punch(role, sockets)
        self.finalize_sockets(sockets)
        return sockets, peer_info
