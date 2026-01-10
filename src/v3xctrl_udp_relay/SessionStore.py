import sqlite3
import string
import secrets

from v3xctrl_udp_relay.helper import init_db


class SessionStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        init_db(self.db_path)

    def get(self, discord_user_id: str) -> tuple[str, str] | None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, spectator_id FROM allowed_sessions WHERE discord_user_id = ?", (discord_user_id,))
            row = cur.fetchone()

            return (row[0], row[1]) if row else None

    def _generate_unique_id(self, column: str) -> str:
        alphabet = string.ascii_lowercase + string.digits
        for _ in range(5):
            generated_id = ''.join(secrets.choice(alphabet) for _ in range(10))
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM allowed_sessions WHERE id = ? OR spectator_id = ?",
                    (generated_id, generated_id)
                )
                if not cur.fetchone():
                    return generated_id

        raise RuntimeError(f"Failed to generate a unique {column} after multiple attempts")

    def create(self, discord_user_id: str, username: str) -> tuple[str, str]:
        for _ in range(5):
            session_id = self._generate_unique_id('id')
            spectator_id = self._generate_unique_id('spectator_id')

            if session_id != spectator_id:
                break
        else:
            raise RuntimeError("Failed to generate different session_id and spectator_id after multiple attempts")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    '''
                    INSERT INTO allowed_sessions (id, spectator_id, discord_user_id, discord_username)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (session_id, spectator_id, discord_user_id, username)
                )
                conn.commit()

                return (session_id, spectator_id)

        except sqlite3.IntegrityError as e:
            if "discord_user_id" in str(e):
                raise RuntimeError(f"Session already exists for user {discord_user_id}")

            raise RuntimeError("Database integrity error occurred")

    def update(self, discord_user_id: str, username: str) -> tuple[str, str]:
        for _ in range(5):
            session_id = self._generate_unique_id('id')
            spectator_id = self._generate_unique_id('spectator_id')

            if session_id != spectator_id:
                break
        else:
            raise RuntimeError("Failed to generate different session_id and spectator_id after multiple attempts")

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                '''
                UPDATE allowed_sessions
                SET id = ?, spectator_id = ?, discord_username = ?
                WHERE discord_user_id = ?
                ''',
                (session_id, spectator_id, username, discord_user_id)
            )
            conn.commit()

            return (session_id, spectator_id)

    def exists(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM allowed_sessions WHERE id = ?", (session_id,))

            return cur.fetchone() is not None

    def get_session_id_from_spectator_id(self, spectator_id: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM allowed_sessions WHERE spectator_id = ?", (spectator_id,))
            row = cur.fetchone()

            return row[0] if row else None
