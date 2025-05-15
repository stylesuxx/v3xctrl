import threading
import time

from punch import PunchPeer
from rpi_4g_streamer.Message import ServerAnnouncement, Ack

VIDEO_PORT = 12345
CONTROL_PORT = 12346

RENDEZVOUS_SERVER = 'rendezvous.websium.at'
RENDEZVOUS_PORT = 8888
ID = "test123"


class PunchServer(PunchPeer):
    def run(self):
        video_sock = self.bind_socket("VIDEO", VIDEO_PORT)
        control_sock = self.bind_socket("CONTROL", CONTROL_PORT)

        video_result = [None]
        control_result = [None]

        def reg_wrapper(sock, port_type: str, result_holder):
            announcement = ServerAnnouncement(i=self.session_id, p=port_type)
            result_holder[0] = self.register_with_rendezvous(sock, announcement)

        t1 = threading.Thread(target=reg_wrapper, args=(video_sock, "video", video_result))
        t2 = threading.Thread(target=reg_wrapper, args=(control_sock, "control", control_result))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        if not video_result[0] or not control_result[0]:
            print("[!] Registration failed")
            return

        client_ip = video_result[0].get_ip()
        client_video_port = video_result[0].get_video_port()
        client_control_port = control_result[0].get_control_port()

        for _ in range(3):
            video_sock.sendto(b'poke-video', (client_ip, client_video_port))
            control_sock.sendto(b'poke-control', (client_ip, client_control_port))
            time.sleep(0.3)

        print(f"[✓] Ready to receive from client:")
        print(f"    VIDEO: {client_ip}:{client_video_port}")
        print(f"    CONTROL: {client_ip}:{client_control_port}")

        video_sock.settimeout(None)
        control_sock.settimeout(None)

        threading.Thread(target=self.video_listener, args=(video_sock,), daemon=True).start()
        self.control_listener(control_sock)

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
