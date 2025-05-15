import threading
import time

from punch import PunchPeer
from rpi_4g_streamer.Message import ClientAnnouncement, PeerInfo, Syn

RENDEZVOUS_SERVER = 'rendezvous.websium.at'
RENDEZVOUS_PORT = 8888
ID = "test123"

VIDEO_INTERVAL = 1
CONTROL_INTERVAL = 1


class PunchClient(PunchPeer):
    def run(self):
        video_sock = self.bind_socket("VIDEO")
        control_sock = self.bind_socket("CONTROL")

        info = self.register_with_rendezvous(video_sock, ClientAnnouncement(self.session_id))

        if not isinstance(info, PeerInfo) or not isinstance(info, PeerInfo):
            print("[!] Invalid peer info received")
            return

        server_ip = info.get_ip()
        video_port = info.get_video_port()
        control_port = info.get_control_port()

        video_sock.settimeout(None)
        control_sock.settimeout(None)

        print(f"[✓] Server IP: {server_ip}")
        print(f"    VIDEO port: {video_port}")
        print(f"    CONTROL port: {control_port}")

        threading.Thread(target=self.video_sender, args=(video_sock, server_ip, video_port), daemon=True).start()
        self.control_loop(control_sock, server_ip, control_port)

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
