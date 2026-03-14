import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from manage_users import cmd_add, cmd_list, cmd_remove, load_users, save_users


class TestLoadSaveUsers(unittest.TestCase):
    def test_load_nonexistent_file(self):
        users = load_users('/nonexistent/path.json')
        self.assertEqual(users, {})

    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name

        try:
            save_users(path, {'alice': 'hash1', 'bob': 'hash2'})
            users = load_users(path)
            self.assertEqual(users, {'alice': 'hash1', 'bob': 'hash2'})
        finally:
            os.unlink(path)


class TestCmdAdd(unittest.TestCase):
    def test_add_new_user(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            path = f.name

        try:
            args = type('Args', (), {'file': path, 'username': 'newuser'})()
            cmd_add(args)

            users = load_users(path)
            self.assertIn('newuser', users)
            self.assertIsNone(users['newuser'])
        finally:
            os.unlink(path)

    def test_add_existing_user_resets_password(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'existing': 'somehash'}, f)
            path = f.name

        try:
            args = type('Args', (), {'file': path, 'username': 'existing'})()
            cmd_add(args)

            users = load_users(path)
            self.assertIn('existing', users)
            self.assertIsNone(users['existing'])
        finally:
            os.unlink(path)


class TestCmdRemove(unittest.TestCase):
    def test_remove_existing_user(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'alice': 'hash1', 'bob': 'hash2'}, f)
            path = f.name

        try:
            args = type('Args', (), {'file': path, 'username': 'alice'})()
            cmd_remove(args)

            users = load_users(path)
            self.assertNotIn('alice', users)
            self.assertIn('bob', users)
        finally:
            os.unlink(path)

    def test_remove_nonexistent_user(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            path = f.name

        try:
            args = type('Args', (), {'file': path, 'username': 'ghost'})()
            with self.assertRaises(SystemExit):
                cmd_remove(args)
        finally:
            os.unlink(path)


class TestCmdList(unittest.TestCase):
    def test_list_users(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'alice': 'h1', 'bob': 'h2'}, f)
            path = f.name

        try:
            args = type('Args', (), {'file': path})()
            with patch('builtins.print') as mock_print:
                cmd_list(args)
            calls = [str(c) for c in mock_print.call_args_list]
            self.assertTrue(any('alice' in c for c in calls))
            self.assertTrue(any('bob' in c for c in calls))
        finally:
            os.unlink(path)

    def test_list_empty(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            path = f.name

        try:
            args = type('Args', (), {'file': path})()
            with patch('builtins.print') as mock_print:
                cmd_list(args)
            mock_print.assert_called_once_with('No users configured')
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
