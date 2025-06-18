import logging
import sqlite3
import string
import secrets

from v3xctrl_udp_relay.helper import init_db


class SessionStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        init_db(self.db_path)

    def get(self, discord_user_id: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM allowed_sessions WHERE discord_user_id = ?", (discord_user_id,))
            row = cur.fetchone()

            return row[0] if row else None

    def create(self, discord_user_id: str, username: str) -> str:
        alphabet = string.ascii_lowercase + string.digits
        for _ in range(5):
            session_id = ''.join(secrets.choice(alphabet) for _ in range(10))
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM allowed_sessions WHERE id = ?", (session_id,))
                if not cur.fetchone():
                    cur.execute(
                        '''
                        INSERT INTO allowed_sessions (id, discord_user_id, discord_username)
                        VALUES (?, ?, ?)
                        ''',
                        (session_id, discord_user_id, username)
                    )
                    conn.commit()
                    logging.info(f"Whitelisted session {session_id} for {username} ({discord_user_id})")

                    return session_id

        raise RuntimeError("Failed to generate unique session ID")

    def exists(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM allowed_sessions WHERE id = ?", (session_id,))
            return cur.fetchone() is not None
