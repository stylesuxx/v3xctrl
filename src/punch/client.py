import argparse
import threading
import time

from punch import PunchPeer
from rpi_4g_streamer.Message import Syn

VIDEO_PORT = 26666
CONTROL_PORT = 26668

DEFAULT_RENDEZVOUS_SERVER = 'rendezvous.websium.at'
# DEFAULT_RENDEZVOUS_SERVER = '192.168.1.100'
DEFAULT_RENDEZVOUS_PORT = 8888


class PunchClient(PunchPeer):
    def run(self):
        ports = {
            "video": VIDEO_PORT,
            "control": CONTROL_PORT
        }

        sockets, peer_info = self.setup("client", ports)

        ip = peer_info["video"].get_ip()
        vp, cp = peer_info["video"].get_video_port(), peer_info["control"].get_control_port()

        print(f"[✓] Server IP: {ip}")
        print(f"    VIDEO port: {vp}")
        print(f"    CONTROL port: {cp}")

        threading.Thread(target=self.video_sender, args=(sockets["video"], ip, vp), daemon=True).start()
        self.control_loop(sockets["control"], ip, cp)

    def video_sender(self, sock, ip, port):
        while True:
            sock.sendto(Syn().to_bytes(), (ip, port))
            print(f"[→] Sent to {ip}:{port}")
            time.sleep(1)

    def control_loop(self, sock, ip, port):
        def receiver():
            while True:
                _, addr = sock.recvfrom(1024)
                print(f"[C] from {addr[0]}:{addr[1]}")

        threading.Thread(target=receiver, daemon=True).start()

        while True:
            sock.sendto(Syn().to_bytes(), (ip, port))
            print(f"[→] Sent to {ip}:{port}")
            time.sleep(1)


def parse_args():
    parser = argparse.ArgumentParser(description="UDP Punch Server")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--server", default=DEFAULT_RENDEZVOUS_SERVER, help="Rendezvous server address")
    parser.add_argument("--port", type=int, default=DEFAULT_RENDEZVOUS_PORT, help="Rendezvous server port")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    PunchClient(args.server, args.port, args.id).run()
