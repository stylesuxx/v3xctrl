"""
Client and Server keep announcing themselves. Timestamps are updated with each
new announce, so as long as announcements are coming in, the session will not
expire.
"""

import socket
import threading
import time

from rpi_4g_streamer.Message import Message, ClientAnnouncement, ServerAnnouncement, PeerInfo  # Adjust path as needed


PORT = 8888
TIMEOUT = 10
CLEANUP_INTERVAL = 5

# session_id -> {'server': {'video': {...}, 'control': {...}}, 'client': {...}}
sessions = {}
lock = threading.Lock()
valid_types = ["video", "control"]


def clean_expired_sessions():
    """
    Remove session if all entries are expired.
    """
    while True:
        now = time.time()
        with lock:
            expired = []
            for session_id, session in sessions.items():
                entries = []
                if 'client' in session:
                    entries.append(session['client'])
                if 'server' in session:
                    entries += session['server'].values()

                if all(now - entry['ts'] > TIMEOUT for entry in entries):
                    expired.append(session_id)

            for session_id in expired:
                print(f"[~] Remove expired session: {session_id}")
                del sessions[session_id]

        time.sleep(CLEANUP_INTERVAL)


def main():
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

            with lock:
                if isinstance(msg, ServerAnnouncement):
                    session_id = msg.get_id()
                    port_type = msg.get_port_type()

                    if port_type not in valid_types:
                        print(f"[!] Invalid server type '{port_type}' from {addr}")
                        continue

                    session = sessions.setdefault(session_id, {})
                    session.setdefault("server", {})
                    session["server"][port_type] = {
                        "addr": addr,
                        "ts": time.time()
                    }

                    print(f"[+] Registered SERVER for session '{session_id}' from {addr} ({port_type})")

                elif isinstance(msg, ClientAnnouncement):
                    session_id = msg.get_id()
                    session = sessions.setdefault(session_id, {})
                    session["client"] = {
                        "addr": addr,
                        "ts": time.time()
                    }
                    print(f"[+] Registered CLIENT for session '{session_id}' from {addr}")

                else:
                    print(f"[!] Unknown or unsupported message type from {addr}: {msg.type}")
                    continue

                # Check if all roles are present
                session_id = msg.get_id()
                session = sessions.get(session_id, {})

                if "client" in session and "server" in session and \
                   "video" in session["server"] and \
                   "control" in session["server"]:

                    client_addr = session["client"]["addr"]
                    video_addr = session["server"]["video"]["addr"]
                    control_addr = session["server"]["control"]["addr"]

                    # Send PeerInfo to client
                    peer_info_client = PeerInfo(
                        ip=video_addr[0],
                        video_port=video_addr[1],
                        control_port=control_addr[1]
                    )
                    sock.sendto(peer_info_client.to_bytes(), client_addr)

                    # Send PeerInfo to both server sockets
                    for role_type in ["video", "control"]:
                        peer_info_server = PeerInfo(
                            ip=client_addr[0],
                            video_port=client_addr[1],
                            control_port=client_addr[1]  # Simplified: same port for both on client side
                        )
                        sock.sendto(peer_info_server.to_bytes(), session["server"][role_type]["addr"])

                    print(f"[✓] Matched session '{session_id}': "
                          f"server {video_addr[0]} ↔ client {client_addr[0]}")

                    del sessions[session_id]

        except Exception as e:
            print(f"[!] Error: {e}")


if __name__ == "__main__":
    main()
