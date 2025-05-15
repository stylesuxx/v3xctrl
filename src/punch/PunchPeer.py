import socket
import json
import time


class PunchPeer:
    RENDEZVOUS_SERVER = '192.168.1.100'
    RENDEZVOUS_PORT = 8888
    REGISTER_TIMEOUT = 60
    ANNOUNCE_INTERVAL = 5

    def __init__(self, session_id):
        self.session_id = session_id

    def bind_socket(self, name, port=0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        print(f"[+] Bound {name} socket to {sock.getsockname()}")
        return sock

    def register_with_rendezvous(self, sock, role, type_str=None):
        msg = {
            "role": role,
            "id": self.session_id
        }
        if type_str:
            msg["type"] = type_str

        sock.settimeout(1)
        start_time = time.time()

        while time.time() - start_time < self.REGISTER_TIMEOUT:
            try:
                sock.sendto(json.dumps(msg).encode(), (self.RENDEZVOUS_SERVER, self.RENDEZVOUS_PORT))
                print(f"[→] Sent {role.upper()} registration ({type_str}) from {sock.getsockname()[1]}")

                data, _ = sock.recvfrom(1024)
                info = json.loads(data.decode())
                print(f"[✓] Got peer info ({type_str}): {info}")
                return info
            except socket.timeout:
                time.sleep(self.ANNOUNCE_INTERVAL)
            except Exception as e:
                print(f"[!] Registration error ({type_str}): {e}")
                return None

        print(f"[!] Timeout registering {type_str}")
        return None
