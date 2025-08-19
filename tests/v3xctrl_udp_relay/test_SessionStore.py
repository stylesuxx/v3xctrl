import os
import tempfile
import sqlite3

import unittest
from unittest.mock import patch

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.helper import init_db


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".sqlite", prefix="testing_")
        os.close(self.db_fd)
        init_db(self.db_path)
        self.store = SessionStore(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_get_returns_none_if_not_found(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_create_and_get(self):
        user_id = "42"
        username = "tester"

        session_id = self.store.create(user_id, username)
        self.assertTrue(session_id)
        self.assertEqual(self.store.get(user_id), session_id)

    def test_create_twice_same_user_raises(self):
        user_id = "42"
        username = "tester"

        self.store.create(user_id, username)
        with self.assertRaises(RuntimeError):
            self.store.create(user_id, username)

    def test_create_max_attempts_exceeded(self):
        # Manually insert a session to guarantee collision
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO allowed_sessions (id, discord_user_id, discord_username) VALUES (?, ?, ?)",
                ("aaaaaaaaaa", "existing_user", "existing")
            )
            conn.commit()

        # Mock to always return 'a' so generated ID is always "aaaaaaaaaa"
        with patch('v3xctrl_udp_relay.SessionStore.secrets.choice') as mock_choice:
            mock_choice.return_value = 'a'

            with self.assertRaises(RuntimeError) as context:
                self.store.create("new_user", "new_username")

            self.assertIn("Failed to generate a unique session ID", str(context.exception))

    def test_create_id_collision_continues_retry(self):
        # Manually insert a session
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO allowed_sessions (id, discord_user_id, discord_username) VALUES (?, ?, ?)",
                ("aaaaaaaaaa", "existing_user", "existing")
            )
            conn.commit()

        with patch('v3xctrl_udp_relay.SessionStore.secrets.choice') as mock_choice:
            call_count = 0
            def side_effect(seq):
                nonlocal call_count
                call_count += 1
                if call_count <= 10:  # First attempt: all 'a' (collision)
                    return 'a'
                else:  # Second attempt: all 'b' (success)
                    return 'b'

            mock_choice.side_effect = side_effect

            new_session = self.store.create("new_user", "new_username")
            self.assertEqual(new_session, "bbbbbbbbbb")

    def test_exists_true_for_existing_session(self):
        session_id = self.store.create("user", "username")
        self.assertTrue(self.store.exists(session_id))

    def test_exists_false_for_nonexistent_session(self):
        self.assertFalse(self.store.exists("nonexistent_session"))


if __name__ == "__main__":
    unittest.main()
