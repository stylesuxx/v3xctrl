import sqlite3
import string
import secrets

from v3xctrl_udp_relay.helper import init_db


class SessionStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        init_db(self.db_path)

    def get(self, discord_user_id: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM allowed_sessions WHERE discord_user_id = ?", (discord_user_id,))
            row = cur.fetchone()

            return row[0] if row else None

    def _generate_unique_session_id(self) -> str:
        """Generate a unique session ID that doesn't exist in the database"""
        alphabet = string.ascii_lowercase + string.digits
        for _ in range(5):
            session_id = ''.join(secrets.choice(alphabet) for _ in range(10))
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM allowed_sessions WHERE id = ?", (session_id,))
                if not cur.fetchone():
                    return session_id

        raise RuntimeError("Failed to generate a unique session ID after multiple attempts")

    def create(self, discord_user_id: str, username: str) -> str:
        session_id = self._generate_unique_session_id()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    '''
                    INSERT INTO allowed_sessions (id, discord_user_id, discord_username)
                    VALUES (?, ?, ?)
                    ''',
                    (session_id, discord_user_id, username)
                )
                conn.commit()

                return session_id

        except sqlite3.IntegrityError as e:
            if "discord_user_id" in str(e):
                raise RuntimeError(f"Session already exists for user {discord_user_id}")

            raise RuntimeError("Database integrity error occurred")

    def update(self, discord_user_id: str, username: str) -> str:
        session_id = self._generate_unique_session_id()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                '''
                UPDATE allowed_sessions
                SET id = ?, discord_username = ?
                WHERE discord_user_id = ?
                ''',
                (session_id, username, discord_user_id)
            )
            conn.commit()

            return session_id

    def exists(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM allowed_sessions WHERE id = ?", (session_id,))

            return cur.fetchone() is not None
