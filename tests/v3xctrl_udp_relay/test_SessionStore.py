import os
import sqlite3
import tempfile
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

        session_id, spectator_id = self.store.create(user_id, username)
        self.assertTrue(session_id)
        self.assertTrue(spectator_id)
        self.assertNotEqual(session_id, spectator_id)
        self.assertEqual(self.store.get(user_id), (session_id, spectator_id))

    def test_create_twice_same_user_raises(self):
        user_id = "42"
        username = "tester"

        self.store.create(user_id, username)
        with self.assertRaises(RuntimeError):
            self.store.create(user_id, username)

    def test_create_max_attempts_exceeded(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO allowed_sessions (id, spectator_id, discord_user_id, discord_username) "
                "VALUES (?, ?, ?, ?)",
                ("aaaaaaaaaa", "bbbbbbbbbb", "existing_user", "existing")
            )
            conn.commit()

        with patch('secrets.choice') as mock_choice:
            mock_choice.return_value = 'a'

            with self.assertRaises(RuntimeError) as context:
                self.store.create("new_user", "new_username")

            self.assertIn("Failed to generate a unique", str(context.exception))

    def test_create_ensures_different_ids(self):
        session_id, spectator_id = self.store.create("user1", "username1")
        self.assertTrue(session_id)
        self.assertTrue(spectator_id)
        self.assertNotEqual(session_id, spectator_id)

    def test_update_existing_user(self):
        user_id = "42"
        username = "tester"

        original_session_id, original_spectator_id = self.store.create(user_id, username)
        updated_session_id, updated_spectator_id = self.store.update(user_id, "updated_username")

        self.assertNotEqual(original_session_id, updated_session_id)
        self.assertNotEqual(original_spectator_id, updated_spectator_id)
        self.assertEqual(self.store.get(user_id), (updated_session_id, updated_spectator_id))

    def test_update_nonexistent_user_returns_id_but_no_db_entry(self):
        user_id = "nonexistent"
        session_id, spectator_id = self.store.update(user_id, "username")

        self.assertTrue(session_id)
        self.assertTrue(spectator_id)
        self.assertIsNone(self.store.get(user_id))

    def test_update_max_attempts_exceeded(self):
        self.store.create("42", "tester")

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO allowed_sessions (id, spectator_id, discord_user_id, discord_username) "
                "VALUES (?, ?, ?, ?)",
                ("aaaaaaaaaa", "bbbbbbbbbb", "other_user", "other")
            )
            conn.commit()

        with patch('secrets.choice') as mock_choice:
            mock_choice.return_value = 'a'

            with self.assertRaises(RuntimeError) as context:
                self.store.update("42", "updated_username")

            self.assertIn("Failed to generate a unique", str(context.exception))

    def test_update_ensures_different_ids(self):
        self.store.create("42", "tester")
        session_id, spectator_id = self.store.update("42", "updated_username")
        self.assertTrue(session_id)
        self.assertTrue(spectator_id)
        self.assertNotEqual(session_id, spectator_id)

    def test_exists_true_for_existing_session(self):
        session_id, spectator_id = self.store.create("user", "username")
        self.assertTrue(self.store.exists(session_id))

    def test_exists_false_for_nonexistent_session(self):
        self.assertFalse(self.store.exists("nonexistent_session"))

    def test_get_session_id_from_spectator_id(self):
        session_id, spectator_id = self.store.create("user", "username")
        retrieved_session_id = self.store.get_session_id_from_spectator_id(spectator_id)
        self.assertEqual(retrieved_session_id, session_id)

    def test_get_session_id_from_spectator_id_nonexistent(self):
        retrieved_session_id = self.store.get_session_id_from_spectator_id("nonexistent")
        self.assertIsNone(retrieved_session_id)


if __name__ == "__main__":
    unittest.main()
