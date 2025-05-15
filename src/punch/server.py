import threading
import time

from punch import PunchPeer
from rpi_4g_streamer.Message import PeerInfo, Ack

VIDEO_PORT = 12345
CONTROL_PORT = 12346

RENDEZVOUS_SERVER = 'rendezvous.websium.at'
# RENDEZVOUS_SERVER = '192.168.1.100'
RENDEZVOUS_PORT = 8888
ID = "test123"


class PunchServer(PunchPeer):
    def run(self):
        # Bind fixed ports for server
        sockets = {
            "video": self.bind_socket("VIDEO", VIDEO_PORT),
            "control": self.bind_socket("CONTROL", CONTROL_PORT)
        }

        peer_info = self.register_all(sockets, role="server")

        if not all(isinstance(p, PeerInfo) for p in peer_info.values()):
            print("[!] Registration failed")
            return

        self.send_pokes(sockets, peer_info["video"])

        client_ip = peer_info["video"].get_ip()
        client_video_port = peer_info["video"].get_video_port()
        client_control_port = peer_info["control"].get_control_port()

        print(f"[✓] Ready to receive from client:")
        print(f"    VIDEO: {client_ip}:{client_video_port}")
        print(f"    CONTROL: {client_ip}:{client_control_port}")

        sockets["video"].settimeout(None)
        sockets["control"].settimeout(None)

        threading.Thread(target=self.video_listener, args=(sockets["video"],), daemon=True).start()
        self.control_listener(sockets["control"])

    def video_listener(self, sock):
        print(f"[V] Listening on {sock.getsockname()}")
        while True:
            data, addr = sock.recvfrom(2048)
            print(f"[V] from {addr}")

    def control_listener(self, sock):
        print(f"[C] Listening on {sock.getsockname()}")
        while True:
            data, addr = sock.recvfrom(1024)
            print(f"[C] from {addr}")
            sock.sendto(Ack().to_bytes(), addr)


if __name__ == "__main__":
    PunchServer(RENDEZVOUS_SERVER, RENDEZVOUS_PORT, ID).run()
