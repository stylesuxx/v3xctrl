import socket
import threading
import time

from punch import PunchPeer
from rpi_4g_streamer.Message import PeerInfo, Syn

RENDEZVOUS_SERVER = 'rendezvous.websium.at'
# RENDEZVOUS_SERVER = '192.168.1.100'
RENDEZVOUS_PORT = 8888
ID = "test123"

PREDEFINED_VIDEO_PORT = 45000
VIDEO_INTERVAL = 1
CONTROL_INTERVAL = 1


class PunchClient(PunchPeer):
    def run(self):
        # Set up sockets
        sockets = {
            "video": socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
            "control": self.bind_socket("CONTROL")
        }
        sockets["video"].bind(('', PREDEFINED_VIDEO_PORT))
        print(f"[+] Bound VIDEO socket to {sockets['video'].getsockname()}")

        # Register both
        peer_info = self.register_all(sockets, role="client")

        if not all(isinstance(p, PeerInfo) for p in peer_info.values()):
            print("[!] Invalid peer info received")
            return

        server_ip = peer_info["video"].get_ip()
        video_port = peer_info["video"].get_video_port()
        control_port = peer_info["control"].get_control_port()

        sockets["video"].settimeout(None)
        sockets["control"].settimeout(None)

        print(f"[✓] Server IP: {server_ip}")
        print(f"    VIDEO port: {video_port}")
        print(f"    CONTROL port: {control_port}")

        threading.Thread(target=self.video_sender, args=(sockets["video"], server_ip, video_port), daemon=True).start()
        self.control_loop(sockets["control"], server_ip, control_port)

    def video_sender(self, sock, ip, port):
        while True:
            sock.sendto(Syn().to_bytes(), (ip, port))
            print(f"[→] Sent to {ip}:{port}")
            time.sleep(VIDEO_INTERVAL)

    def control_loop(self, sock, ip, port):
        def receiver():
            while True:
                _, addr = sock.recvfrom(1024)
                print(f"[C] from {addr[0]}:{addr[1]}")

        threading.Thread(target=receiver, daemon=True).start()

        while True:
            sock.sendto(Syn().to_bytes(), (ip, port))
            print(f"[→] Sent to {ip}:{port}")
            time.sleep(CONTROL_INTERVAL)


if __name__ == "__main__":
    PunchClient(RENDEZVOUS_SERVER, RENDEZVOUS_PORT, ID).run()
