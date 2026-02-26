import logging
import socket
import sqlite3

from v3xctrl_control.message import ConnectionTest, ConnectionTestAck, Message


def init_db(path: str) -> None:
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS allowed_sessions (
                id TEXT PRIMARY KEY,
                spectator_id TEXT NOT NULL UNIQUE,
                discord_user_id TEXT NOT NULL UNIQUE,
                discord_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    logging.info("Database initialized or already exists.")


def test_relay_connection(
    server: str,
    port: int,
    session_id: str,
    spectator_mode: bool = False
) -> tuple[bool, str]:
    """
    Test connectivity to relay server and validate session/spectator ID.

    Sends up to 10 ConnectionTest packets (500ms apart). Returns as soon as
    the first ConnectionTestAck is received.

    Returns:
        Tuple of (success, user_message)
    """
    test_msg = ConnectionTest(i=session_id, s=spectator_mode)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)

    try:
        for _ in range(10):
            sock.sendto(test_msg.to_bytes(), (server, port))

            try:
                data, _ = sock.recvfrom(1024)
                response = Message.from_bytes(data)

                if isinstance(response, ConnectionTestAck):
                    if response.valid:
                        id_type = "spectator ID" if spectator_mode else "session ID"
                        return (True, f"Valid {id_type}")
                    else:
                        id_type = "spectator ID" if spectator_mode else "session ID"
                        return (False, f"Invalid {id_type}")
            except socket.timeout:
                continue
            except ValueError:
                continue

        return (False, "Could not connect. Check your server URL and firewall settings.")

    except socket.gaierror:
        return (False, "Could not resolve relay server hostname.")

    except Exception as e:
        return (False, f"Connection test failed: {e}")

    finally:
        sock.close()
