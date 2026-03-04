import json
import os
import tempfile
import unittest

from werkzeug.security import check_password_hash, generate_password_hash

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import create_app


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.users_fd, self.users_file = tempfile.mkstemp(suffix='.json')
        users = {
            'admin': generate_password_hash('secret123'),
            'viewer': generate_password_hash('viewpass'),
            'newuser': None,
        }
        with open(self.users_file, 'w') as f:
            json.dump(users, f)

        self.app = create_app(
            relay_ports=[8888],
            users_file=self.users_file,
            secret_key='test-secret-key',
        )
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.users_fd)
        os.unlink(self.users_file)

    def test_dashboard_redirects_to_login_when_not_authenticated(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_login_page_renders(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)

    def test_login_success(self):
        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'secret123',
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/', response.headers['Location'])

    def test_login_wrong_password(self):
        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'wrongpass',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password', response.data)

    def test_login_unknown_user(self):
        response = self.client.post('/login', data={
            'username': 'nonexistent',
            'password': 'anything',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password', response.data)

    def test_login_redirects_to_dashboard_when_already_authenticated(self):
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin'
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 302)

    def test_logout(self):
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin'
        response = self.client.post('/logout', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_api_stats_requires_auth(self):
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_null_password_redirects_to_set_password(self):
        response = self.client.post('/login', data={
            'username': 'newuser',
            'password': '',
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/set-password', response.headers['Location'])

    def test_set_password_page_renders(self):
        with self.client.session_transaction() as sess:
            sess['pending_password_setup'] = 'newuser'
        response = self.client.get('/set-password')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'newuser', response.data)

    def test_set_password_without_pending_session_redirects(self):
        response = self.client.get('/set-password')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_set_password_saves_and_logs_in(self):
        with self.client.session_transaction() as sess:
            sess['pending_password_setup'] = 'newuser'
        response = self.client.post('/set-password', data={
            'password': 'mypassword',
            'confirm': 'mypassword',
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/', response.headers['Location'])

        with open(self.users_file) as f:
            users = json.load(f)
        self.assertIsNotNone(users['newuser'])
        self.assertTrue(check_password_hash(users['newuser'], 'mypassword'))

    def test_set_password_rejects_mismatch(self):
        with self.client.session_transaction() as sess:
            sess['pending_password_setup'] = 'newuser'
        response = self.client.post('/set-password', data={
            'password': 'pass1',
            'confirm': 'pass2',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Passwords do not match', response.data)

    def test_set_password_rejects_empty(self):
        with self.client.session_transaction() as sess:
            sess['pending_password_setup'] = 'newuser'
        response = self.client.post('/set-password', data={
            'password': '',
            'confirm': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password cannot be empty', response.data)

    def test_missing_users_file(self):
        os.unlink(self.users_file)
        # Re-create fd so tearDown doesn't fail
        self.users_fd, self.users_file = tempfile.mkstemp(suffix='.json')

        app = create_app(
            relay_ports=[8888],
            users_file='/nonexistent/users.json',
            secret_key='test-secret-key',
        )
        app.config['TESTING'] = True
        client = app.test_client()

        response = client.post('/login', data={
            'username': 'admin',
            'password': 'secret123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password', response.data)


if __name__ == '__main__':
    unittest.main()
