import threading
import time

from punch import PunchPeer

VIDEO_INTERVAL = 1
CONTROL_INTERVAL = 1
ID = "test123"


class PunchClient(PunchPeer):
    def run(self):
        video_sock = self.bind_socket("VIDEO")
        control_sock = self.bind_socket("CONTROL")

        video_info = self.register_with_rendezvous(video_sock, "client")
        control_info = self.register_with_rendezvous(control_sock, "client")

        if not video_info or 'peer_ip' not in video_info or 'ports' not in video_info:
            print("[!] Invalid peer info received")
            return

        server_ip = video_info['peer_ip']
        video_port, control_port = video_info['ports']

        video_sock.settimeout(None)
        control_sock.settimeout(None)

        print(f"[✓] Server IP: {server_ip}")
        print(f"    VIDEO port: {video_port}")
        print(f"    CONTROL port: {control_port}")

        threading.Thread(target=self.video_sender, args=(video_sock, server_ip, video_port), daemon=True).start()
        self.control_loop(control_sock, server_ip, control_port)

    def video_sender(self, sock, ip, port):
        while True:
            sock.sendto(b"VIDEO_FRAME", (ip, port))
            print(f"[→] Sent VIDEO_FRAME to {ip}:{port}")
            time.sleep(VIDEO_INTERVAL)

    def control_loop(self, sock, ip, port):
        def receiver():
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    decoded = data.decode(errors='ignore')
                    print(f"[←] CONTROL response from {addr}: {decoded}")
                except Exception as e:
                    print(f"[!] Control receive error: {e}")
                    break

        threading.Thread(target=receiver, daemon=True).start()

        while True:
            sock.sendto(b"CONTROL_PING", (ip, port))
            print(f"[→] Sent CONTROL_PING to {ip}:{port}")
            time.sleep(CONTROL_INTERVAL)


if __name__ == "__main__":
    PunchClient(ID).run()
