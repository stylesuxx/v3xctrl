import socket
import threading
import time

from v3xctrl_helper import Address
from v3xctrl_control.Message import Message, PeerAnnouncement, PeerInfo

PORT = 8888
TIMEOUT = 10
CLEANUP_INTERVAL = 5

valid_types = ["video", "control"]
roles = ["client", "server"]

sessions = {}
lock = threading.Lock()


def clean_expired_sessions() -> None:
    while True:
        time.sleep(CLEANUP_INTERVAL)
        now = time.time()
        with lock:
            expired = [
                sid for sid, peers in sessions.items()
                if all(
                    now - entry["ts"] > TIMEOUT
                    for role in peers.values()
                    for entry in role.values()
                )
            ]
            for sid in expired:
                print(f"[~] Removed expired session: {sid}")
                del sessions[sid]


def handle_peer_announcement(
    msg: PeerAnnouncement,
    addr: Address,
    sock: socket.socket
) -> None:
    session_id = msg.get_id()
    role = msg.get_role()
    port_type = msg.get_port_type()

    if role not in roles or port_type not in valid_types:
        print(f"[!] Invalid announcement from {addr} — role={role}, port_type={port_type}")
        return

    with lock:
        session = sessions.setdefault(session_id, {})
        role_entry = session.setdefault(role, {})
        role_entry[port_type] = {"addr": addr, "ts": time.time()}

        print(f"[+] Registered {role.upper()} {port_type} for session '{session_id}' from {addr}")

        # Check for full match
        if all(
            role in session and all(pt in session[role] for pt in valid_types)
            for role in roles
        ):
            client = session["client"]
            server = session["server"]

            peer_info_for_client = PeerInfo(
                ip=server["video"]["addr"][0],
                video_port=server["video"]["addr"][1],
                control_port=server["control"]["addr"][1],
            )
            peer_info_for_server = PeerInfo(
                ip=client["video"]["addr"][0],
                video_port=client["video"]["addr"][1],
                control_port=client["control"]["addr"][1],
            )

            for pt in valid_types:
                sock.sendto(peer_info_for_client.to_bytes(), client[pt]["addr"])
                sock.sendto(peer_info_for_server.to_bytes(), server[pt]["addr"])

            print(f"[✓] Matched session '{session_id}': {client['video']['addr'][0]} ↔ {server['video']['addr'][0]}")
            del sessions[session_id]


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', PORT))
    print(f"[+] Rendezvous server listening on UDP port {PORT}")

    threading.Thread(target=clean_expired_sessions, daemon=True).start()
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            try:
                msg = Message.from_bytes(data)
            except Exception:
                print(f"[!] Malformed message from {addr}")
                continue

            if isinstance(msg, PeerAnnouncement):
                handle_peer_announcement(msg, addr, sock)
            else:
                print(f"[!] Unsupported message type from {addr}")

        except Exception as e:
            print(f"[!] Error: {e}")


if __name__ == "__main__":
    main()
