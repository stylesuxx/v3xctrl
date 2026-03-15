import unittest
from unittest.mock import MagicMock, patch, call

from v3xctrl_punch import rendezvouz
from v3xctrl_punch.rendezvouz import (
    PORT,
    TIMEOUT,
    CLEANUP_INTERVAL,
    valid_types,
    roles,
    handle_peer_announcement,
    clean_expired_sessions,
)
from v3xctrl_control.message import Message, PeerInfo


def make_announcement(session_id="session1", role="client", port_type="video"):
    announcement = MagicMock()
    announcement.get_id.return_value = session_id
    announcement.get_role.return_value = role
    announcement.get_port_type.return_value = port_type
    return announcement


class TestModuleConstants(unittest.TestCase):
    def test_port(self):
        self.assertEqual(PORT, 8888)

    def test_timeout(self):
        self.assertEqual(TIMEOUT, 10)

    def test_cleanup_interval(self):
        self.assertEqual(CLEANUP_INTERVAL, 5)

    def test_valid_types(self):
        self.assertEqual(valid_types, ["video", "control"])

    def test_roles(self):
        self.assertEqual(roles, ["client", "server"])


class TestHandlePeerAnnouncement(unittest.TestCase):
    def setUp(self):
        rendezvouz.sessions.clear()

    def tearDown(self):
        rendezvouz.sessions.clear()

    def test_invalid_role_returns_early(self):
        announcement = make_announcement(role="invalid_role")
        sock = MagicMock()
        handle_peer_announcement(announcement, ("1.2.3.4", 5000), sock)
        self.assertEqual(rendezvouz.sessions, {})

    def test_invalid_port_type_returns_early(self):
        announcement = make_announcement(port_type="invalid_type")
        sock = MagicMock()
        handle_peer_announcement(announcement, ("1.2.3.4", 5000), sock)
        self.assertEqual(rendezvouz.sessions, {})

    def test_single_registration_creates_session_entry(self):
        announcement = make_announcement(session_id="s1", role="client", port_type="video")
        sock = MagicMock()
        address = ("10.0.0.1", 6000)

        handle_peer_announcement(announcement, address, sock)

        self.assertIn("s1", rendezvouz.sessions)
        self.assertIn("client", rendezvouz.sessions["s1"])
        self.assertIn("video", rendezvouz.sessions["s1"]["client"])
        self.assertEqual(rendezvouz.sessions["s1"]["client"]["video"]["addr"], address)
        sock.sendto.assert_not_called()

    def test_partial_match_does_not_send(self):
        sock = MagicMock()

        handle_peer_announcement(
            make_announcement(session_id="s1", role="client", port_type="video"),
            ("10.0.0.1", 6000),
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="client", port_type="control"),
            ("10.0.0.1", 6001),
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="server", port_type="video"),
            ("10.0.0.2", 7000),
            sock,
        )

        self.assertIn("s1", rendezvouz.sessions)
        sock.sendto.assert_not_called()

    def test_full_match_sends_peer_info_and_deletes_session(self):
        sock = MagicMock()

        client_video_address = ("10.0.0.1", 6000)
        client_control_address = ("10.0.0.1", 6001)
        server_video_address = ("10.0.0.2", 7000)
        server_control_address = ("10.0.0.2", 7001)

        handle_peer_announcement(
            make_announcement(session_id="s1", role="client", port_type="video"),
            client_video_address,
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="client", port_type="control"),
            client_control_address,
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="server", port_type="video"),
            server_video_address,
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="server", port_type="control"),
            server_control_address,
            sock,
        )

        self.assertNotIn("s1", rendezvouz.sessions)
        self.assertEqual(sock.sendto.call_count, 4)

    def test_full_match_peer_info_content(self):
        sock = MagicMock()

        client_video_address = ("10.0.0.1", 6000)
        client_control_address = ("10.0.0.1", 6001)
        server_video_address = ("10.0.0.2", 7000)
        server_control_address = ("10.0.0.2", 7001)

        handle_peer_announcement(
            make_announcement(session_id="s1", role="client", port_type="video"),
            client_video_address,
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="client", port_type="control"),
            client_control_address,
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="server", port_type="video"),
            server_video_address,
            sock,
        )
        handle_peer_announcement(
            make_announcement(session_id="s1", role="server", port_type="control"),
            server_control_address,
            sock,
        )

        sent_calls = sock.sendto.call_args_list
        sent_by_address = {}
        for sent_call in sent_calls:
            sent_data, sent_address = sent_call[0]
            sent_message = Message.from_bytes(sent_data)
            sent_by_address[sent_address] = sent_message

        client_video_peer_info = sent_by_address[client_video_address]
        self.assertIsInstance(client_video_peer_info, PeerInfo)
        self.assertEqual(client_video_peer_info.ip, "10.0.0.2")
        self.assertEqual(client_video_peer_info.video_port, 7000)
        self.assertEqual(client_video_peer_info.control_port, 7001)

        client_control_peer_info = sent_by_address[client_control_address]
        self.assertIsInstance(client_control_peer_info, PeerInfo)
        self.assertEqual(client_control_peer_info.ip, "10.0.0.2")
        self.assertEqual(client_control_peer_info.video_port, 7000)
        self.assertEqual(client_control_peer_info.control_port, 7001)

        server_video_peer_info = sent_by_address[server_video_address]
        self.assertIsInstance(server_video_peer_info, PeerInfo)
        self.assertEqual(server_video_peer_info.ip, "10.0.0.1")
        self.assertEqual(server_video_peer_info.video_port, 6000)
        self.assertEqual(server_video_peer_info.control_port, 6001)

        server_control_peer_info = sent_by_address[server_control_address]
        self.assertIsInstance(server_control_peer_info, PeerInfo)
        self.assertEqual(server_control_peer_info.ip, "10.0.0.1")
        self.assertEqual(server_control_peer_info.video_port, 6000)
        self.assertEqual(server_control_peer_info.control_port, 6001)


class TestCleanExpiredSessions(unittest.TestCase):
    def setUp(self):
        rendezvouz.sessions.clear()

    def tearDown(self):
        rendezvouz.sessions.clear()

    @patch("v3xctrl_punch.rendezvouz.time")
    def test_expired_sessions_are_removed(self, mock_time):
        mock_time.sleep.side_effect = [None, StopIteration]
        expired_timestamp = 100.0
        mock_time.time.return_value = expired_timestamp + TIMEOUT + 1

        rendezvouz.sessions["expired_session"] = {
            "client": {
                "video": {"addr": ("1.1.1.1", 1000), "ts": expired_timestamp},
                "control": {"addr": ("1.1.1.1", 1001), "ts": expired_timestamp},
            },
            "server": {
                "video": {"addr": ("2.2.2.2", 2000), "ts": expired_timestamp},
                "control": {"addr": ("2.2.2.2", 2001), "ts": expired_timestamp},
            },
        }

        with self.assertRaises(StopIteration):
            clean_expired_sessions()

        self.assertNotIn("expired_session", rendezvouz.sessions)

    @patch("v3xctrl_punch.rendezvouz.time")
    def test_recent_sessions_are_not_removed(self, mock_time):
        mock_time.sleep.side_effect = [None, StopIteration]
        recent_timestamp = 100.0
        mock_time.time.return_value = recent_timestamp + TIMEOUT - 1

        rendezvouz.sessions["recent_session"] = {
            "client": {
                "video": {"addr": ("1.1.1.1", 1000), "ts": recent_timestamp},
                "control": {"addr": ("1.1.1.1", 1001), "ts": recent_timestamp},
            },
            "server": {
                "video": {"addr": ("2.2.2.2", 2000), "ts": recent_timestamp},
                "control": {"addr": ("2.2.2.2", 2001), "ts": recent_timestamp},
            },
        }

        with self.assertRaises(StopIteration):
            clean_expired_sessions()

        self.assertIn("recent_session", rendezvouz.sessions)


if __name__ == "__main__":
    unittest.main()
