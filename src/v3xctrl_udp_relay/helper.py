import sqlite3
import logging


def init_db(path: str) -> None:
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS allowed_sessions (
                id TEXT PRIMARY KEY,
                discord_user_id TEXT NOT NULL,
                discord_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    logging.info("Database initialized or already exists.")
