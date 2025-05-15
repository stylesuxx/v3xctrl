import threading

from punch import PunchPeer

VIDEO_PORT = 12345
CONTROL_PORT = 12346
ID = "test123"


class PunchServer(PunchPeer):
    def run(self):
        video_sock = self.bind_socket("VIDEO", VIDEO_PORT)
        control_sock = self.bind_socket("CONTROL", CONTROL_PORT)

        video_result = [None]
        control_result = [None]

        def reg_wrapper(sock, type_str, result_holder):
            result_holder[0] = self.register_with_rendezvous(sock, "server", type_str)

        t1 = threading.Thread(target=reg_wrapper, args=(video_sock, "video", video_result))
        t2 = threading.Thread(target=reg_wrapper, args=(control_sock, "control", control_result))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        if not video_result[0] or not control_result[0]:
            print("[!] Registration failed")
            return

        client_ip = video_result[0]['peer_ip']
        client_video_port = video_result[0]['peer_port']
        client_control_port = control_result[0]['peer_port']

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
            try:
                decoded = data.decode('utf-8', errors='ignore')
                print(f"[V] from {addr}: {len(data)} bytes | data: {decoded}")
            except Exception:
                print(f"[V] from {addr}: {len(data)} bytes | raw: {data}")

    def control_listener(self, sock):
        print(f"[C] Listening on {sock.getsockname()}")
        while True:
            data, addr = sock.recvfrom(1024)
            try:
                decoded = data.decode('utf-8', errors='ignore')
                print(f"[C] from {addr}: {decoded}")
            except Exception:
                print(f"[C] from {addr}: {data}")
            sock.sendto(b"CONTROL_ACK", addr)


if __name__ == "__main__":
    PunchServer(ID).run()
