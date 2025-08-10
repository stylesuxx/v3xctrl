import unittest
import os
import tempfile
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.helper import init_db


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        # Create a real temp file for SQLite
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".sqlite", prefix="testing_")
        os.close(self.db_fd)  # Close the file descriptor, SQLite will open it
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

if __name__ == "__main__":
    unittest.main()
