import socket
import json
import threading
import time

PORT = 8888

# Time in which a connection has to be established before it is considered
# expired.
TIMEOUT = 300
CLEANUP_INTERVAL = 5

# session_id -> {'server': {'video': {...}, 'control': {...}}, 'client': {...}}
sessions = {}
lock = threading.Lock()

valid_roles = ["server", "client"]
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
                msg = json.loads(data.decode('utf-8'))
            except Exception:
                print(f"[!] Malformed JSON from {addr}")
                continue

            role = msg.get("role")
            session_id = msg.get("id")

            if role not in valid_roles or not session_id:
                print(f"[!] Invalid message from {addr}: {msg}")
                continue

            with lock:
                session = sessions.setdefault(session_id, {})

                if role == "server":
                    reg_type = msg.get("type")
                    if reg_type not in valid_types:
                        print(f"[!] Server message missing 'type': {msg}")
                        continue

                    session.setdefault("server", {})
                    session["server"][reg_type] = {
                        "addr": addr,
                        "ts": time.time(),
                    }

                    print(f"[+] Registered SERVER ({reg_type}) for session '{session_id}' from {addr}")

                elif role == "client":
                    session["client"] = {
                        "addr": addr,
                        "ts": time.time()
                    }
                    print(f"[+] Registered CLIENT for session '{session_id}' from {addr}")

                # Check if all parts are present
                if "client" in session and "server" in session and \
                        "video" in session["server"] and "control" in session["server"]:
                    client_addr = session["client"]["addr"]
                    video_addr = session["server"]["video"]["addr"]
                    control_addr = session["server"]["control"]["addr"]

                    # Send compact peer info to client
                    sock.sendto(json.dumps({
                        "peer_ip": video_addr[0],  # same for both
                        "ports": [video_addr[1], control_addr[1]]
                    }).encode(), client_addr)

                    # Send client info to both server sockets
                    for t in ["video", "control"]:
                        sock.sendto(json.dumps({
                            "peer_ip": client_addr[0],
                            "peer_port": client_addr[1]
                        }).encode(), session["server"][t]["addr"])

                    print(f"[✓] Matched '{session_id}': "
                          f"server: {video_addr[0]}"
                          f"<-> client: {client_addr[0]}")

                    del sessions[session_id]

        except Exception as e:
            print(f"[!] Error: {e}")


if __name__ == "__main__":
    main()
