import time
import unittest
from unittest.mock import patch

from v3xctrl_udp_relay.custom_types import (
    PeerEntry,
    PortType,
    Session,
    SessionNotFoundError,
    SpectatorEntry,
)
from v3xctrl_udp_relay.Role import Role


class TestRole(unittest.TestCase):
    def test_role_values(self):
        self.assertEqual(Role.STREAMER.value, "streamer")
        self.assertEqual(Role.VIEWER.value, "viewer")
        self.assertEqual(Role.SPECTATOR.value, "spectator")

    def test_role_enumeration(self):
        roles = list(Role)
        self.assertEqual(len(roles), 3)
        self.assertIn(Role.STREAMER, roles)
        self.assertIn(Role.VIEWER, roles)
        self.assertIn(Role.SPECTATOR, roles)


class TestPortType(unittest.TestCase):
    def test_port_type_values(self):
        self.assertEqual(PortType.VIDEO.value, "video")
        self.assertEqual(PortType.CONTROL.value, "control")

    def test_port_type_enumeration(self):
        port_types = list(PortType)
        self.assertEqual(len(port_types), 2)
        self.assertIn(PortType.VIDEO, port_types)
        self.assertIn(PortType.CONTROL, port_types)


class TestPeerEntry(unittest.TestCase):
    def test_initialization(self):
        addr = ("192.168.1.1", 8080)
        with patch('time.time', return_value=1234567890.0):
            peer = PeerEntry(addr)

        self.assertEqual(peer.addr, addr)
        self.assertEqual(peer.ts, 1234567890.0)

    def test_initialization_captures_current_time(self):
        addr = ("192.168.1.1", 8080)
        before_time = time.time()
        peer = PeerEntry(addr)
        after_time = time.time()

        self.assertGreaterEqual(peer.ts, before_time)
        self.assertLessEqual(peer.ts, after_time)

    def test_different_addresses(self):
        addr1 = ("192.168.1.1", 8080)
        addr2 = ("10.0.0.1", 9090)

        peer1 = PeerEntry(addr1)
        peer2 = PeerEntry(addr2)

        self.assertNotEqual(peer1.addr, peer2.addr)
        self.assertEqual(peer1.addr, addr1)
        self.assertEqual(peer2.addr, addr2)


class TestSession(unittest.TestCase):
    def setUp(self):
        sid = "session_id"
        self.session = Session(sid)

    def test_initialization(self):
        self.assertIsInstance(self.session.roles, dict)
        self.assertEqual(len(self.session.roles), 2)
        self.assertIn(Role.STREAMER, self.session.roles)
        self.assertIn(Role.VIEWER, self.session.roles)
        self.assertEqual(self.session.roles[Role.STREAMER], {})
        self.assertEqual(self.session.roles[Role.VIEWER], {})

    def test_register_new_peer_returns_true(self):
        addr = ("192.168.1.1", 8080)

        result = self.session.register(Role.STREAMER, PortType.VIDEO, addr)

        self.assertTrue(result)

    def test_register_existing_peer_returns_false(self):
        addr1 = ("192.168.1.1", 8080)
        addr2 = ("192.168.1.2", 8081)

        self.session.register(Role.STREAMER, PortType.VIDEO, addr1)
        result = self.session.register(Role.STREAMER, PortType.VIDEO, addr2)

        self.assertFalse(result)

    def test_register_stores_peer_entry(self):
        addr = ("192.168.1.1", 8080)

        with patch('time.time', return_value=1234567890.0):
            self.session.register(Role.STREAMER, PortType.VIDEO, addr)

        peer_entry = self.session.roles[Role.STREAMER][PortType.VIDEO]
        self.assertIsInstance(peer_entry, PeerEntry)
        self.assertEqual(peer_entry.addr, addr)
        self.assertEqual(peer_entry.ts, 1234567890.0)

    def test_register_overwrites_existing_peer(self):
        addr1 = ("192.168.1.1", 8080)
        addr2 = ("192.168.1.2", 8081)

        with patch('time.time', return_value=1000.0):
            self.session.register(Role.STREAMER, PortType.VIDEO, addr1)

        with patch('time.time', return_value=2000.0):
            self.session.register(Role.STREAMER, PortType.VIDEO, addr2)

        peer_entry = self.session.roles[Role.STREAMER][PortType.VIDEO]
        self.assertEqual(peer_entry.addr, addr2)
        self.assertEqual(peer_entry.ts, 2000.0)

    def test_register_different_roles_and_port_types(self):
        addresses = [
            (Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111)),
            (Role.STREAMER, PortType.CONTROL, ("2.2.2.2", 2222)),
            (Role.VIEWER, PortType.VIDEO, ("3.3.3.3", 3333)),
            (Role.VIEWER, PortType.CONTROL, ("4.4.4.4", 4444)),
        ]

        for role, port_type, addr in addresses:
            result = self.session.register(role, port_type, addr)
            self.assertTrue(result)

        for role, port_type, addr in addresses:
            peer_entry = self.session.roles[role][port_type]
            self.assertEqual(peer_entry.addr, addr)

    def test_is_role_ready_empty_role(self):
        self.assertFalse(self.session.is_role_ready(Role.STREAMER))
        self.assertFalse(self.session.is_role_ready(Role.VIEWER))

    def test_is_role_ready_partial_registration(self):
        addr = ("192.168.1.1", 8080)

        self.session.register(Role.STREAMER, PortType.VIDEO, addr)

        self.assertFalse(self.session.is_role_ready(Role.STREAMER))

    def test_is_role_ready_full_registration(self):
        addr1 = ("192.168.1.1", 8080)
        addr2 = ("192.168.1.2", 8081)

        self.session.register(Role.STREAMER, PortType.VIDEO, addr1)
        self.session.register(Role.STREAMER, PortType.CONTROL, addr2)

        self.assertTrue(self.session.is_role_ready(Role.STREAMER))

    def test_is_role_ready_both_roles_independently(self):
        self.session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.session.register(Role.STREAMER, PortType.CONTROL, ("1.1.1.2", 1112))

        self.assertTrue(self.session.is_role_ready(Role.STREAMER))
        self.assertFalse(self.session.is_role_ready(Role.VIEWER))

        self.session.register(Role.VIEWER, PortType.VIDEO, ("2.2.2.1", 2221))

        self.assertTrue(self.session.is_role_ready(Role.STREAMER))
        self.assertFalse(self.session.is_role_ready(Role.VIEWER))

        self.session.register(Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2222))

        self.assertTrue(self.session.is_role_ready(Role.STREAMER))
        self.assertTrue(self.session.is_role_ready(Role.VIEWER))

    def test_is_ready_empty_session(self):
        self.assertFalse(self.session.is_ready())

    def test_is_ready_partial_registration(self):
        self.session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.assertFalse(self.session.is_ready())

        self.session.register(Role.STREAMER, PortType.CONTROL, ("1.1.1.2", 1112))
        self.assertFalse(self.session.is_ready())

        self.session.register(Role.VIEWER, PortType.VIDEO, ("2.2.2.1", 2221))
        self.assertFalse(self.session.is_ready())

    def test_is_ready_full_registration(self):
        self.session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.session.register(Role.STREAMER, PortType.CONTROL, ("1.1.1.2", 1112))
        self.session.register(Role.VIEWER, PortType.VIDEO, ("2.2.2.1", 2221))
        self.session.register(Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2222))

        self.assertTrue(self.session.is_ready())


class TestSpectatorEntry(unittest.TestCase):
    def test_initialization(self):
        spectator = SpectatorEntry()

        self.assertIsInstance(spectator.ports, dict)
        self.assertEqual(len(spectator.ports), 0)
        self.assertIsInstance(spectator.created_at, float)

    def test_register_port_new(self):
        spectator = SpectatorEntry()
        addr = ("192.168.1.100", 5000)

        result = spectator.register_port(PortType.VIDEO, addr)

        self.assertTrue(result)
        self.assertIn(PortType.VIDEO, spectator.ports)
        self.assertEqual(spectator.ports[PortType.VIDEO].addr, addr)

    def test_register_port_existing(self):
        spectator = SpectatorEntry()
        addr1 = ("192.168.1.100", 5000)
        addr2 = ("192.168.1.101", 5001)

        spectator.register_port(PortType.VIDEO, addr1)
        result = spectator.register_port(PortType.VIDEO, addr2)

        self.assertFalse(result)
        self.assertEqual(spectator.ports[PortType.VIDEO].addr, addr2)

    def test_is_complete_empty(self):
        spectator = SpectatorEntry()
        self.assertFalse(spectator.is_complete())

    def test_is_complete_partial(self):
        spectator = SpectatorEntry()
        spectator.register_port(PortType.VIDEO, ("192.168.1.100", 5000))

        self.assertFalse(spectator.is_complete())

    def test_is_complete_full(self):
        spectator = SpectatorEntry()
        spectator.register_port(PortType.VIDEO, ("192.168.1.100", 5000))
        spectator.register_port(PortType.CONTROL, ("192.168.1.100", 5001))

        self.assertTrue(spectator.is_complete())

    def test_get_addresses(self):
        spectator = SpectatorEntry()
        addr1 = ("192.168.1.100", 5000)
        addr2 = ("192.168.1.100", 5001)

        spectator.register_port(PortType.VIDEO, addr1)
        spectator.register_port(PortType.CONTROL, addr2)

        addresses = spectator.get_addresses()

        self.assertIsInstance(addresses, set)
        self.assertEqual(len(addresses), 2)
        self.assertIn(addr1, addresses)
        self.assertIn(addr2, addresses)


class TestSessionSpectator(unittest.TestCase):
    def setUp(self):
        self.session = Session("test_session")

    def test_register_spectator_new(self):
        addr = ("192.168.1.100", 5000)

        result = self.session.register(Role.SPECTATOR, PortType.VIDEO, addr)

        self.assertTrue(result)
        self.assertEqual(len(self.session.spectators), 1)

    def test_register_spectator_same_ip_different_port(self):
        addr1 = ("192.168.1.100", 5000)
        addr2 = ("192.168.1.100", 5001)

        result1 = self.session.register(Role.SPECTATOR, PortType.VIDEO, addr1)
        result2 = self.session.register(Role.SPECTATOR, PortType.CONTROL, addr2)

        self.assertTrue(result1)  # First port is new
        self.assertTrue(result2)  # Second port is also new
        self.assertEqual(len(self.session.spectators), 1)  # But same spectator
        self.assertTrue(self.session.spectators[0].is_complete())

    def test_register_spectator_different_ip(self):
        addr1 = ("192.168.1.100", 5000)
        addr2 = ("192.168.1.101", 5000)

        self.session.register(Role.SPECTATOR, PortType.VIDEO, addr1)
        result = self.session.register(Role.SPECTATOR, PortType.VIDEO, addr2)

        self.assertTrue(result)  # Different IP, new spectator
        self.assertEqual(len(self.session.spectators), 2)

    def test_register_spectator_does_not_update_last_announcement(self):
        with patch('time.time', return_value=1000.0):
            session = Session("test")

        initial_time = session.last_announcement_at

        with patch('time.time', return_value=2000.0):
            session.register(Role.SPECTATOR, PortType.VIDEO, ("192.168.1.100", 5000))

        self.assertEqual(session.last_announcement_at, initial_time)

    def test_register_viewer_updates_last_announcement(self):
        with patch('time.time', return_value=1000.0):
            session = Session("test")

        with patch('time.time', return_value=2000.0):
            session.register(Role.VIEWER, PortType.VIDEO, ("192.168.1.100", 5000))

        self.assertEqual(session.last_announcement_at, 2000.0)

    def test_is_ready_ignores_spectators(self):
        # Add spectator only
        self.session.register(Role.SPECTATOR, PortType.VIDEO, ("192.168.1.100", 5000))
        self.session.register(Role.SPECTATOR, PortType.CONTROL, ("192.168.1.100", 5001))

        self.assertFalse(self.session.is_ready())

        # Add streamer and viewer
        self.session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.session.register(Role.STREAMER, PortType.CONTROL, ("1.1.1.2", 1112))
        self.session.register(Role.VIEWER, PortType.VIDEO, ("2.2.2.1", 2221))
        self.session.register(Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2222))

        self.assertTrue(self.session.is_ready())

    def test_register_unknown_role_raises_error(self):
        with self.assertRaises(ValueError):
            # Create a mock role that's not in the enum
            self.session.register("invalid_role", PortType.VIDEO, ("1.1.1.1", 1111))


class TestSessionNotFoundError(unittest.TestCase):
    def test_is_exception_subclass(self):
        self.assertTrue(issubclass(SessionNotFoundError, Exception))

    def test_can_be_raised(self):
        with self.assertRaises(SessionNotFoundError):
            raise SessionNotFoundError("test message")

    def test_can_be_raised_with_message(self):
        message = "Session not found"
        with self.assertRaises(SessionNotFoundError) as cm:
            raise SessionNotFoundError(message)

        self.assertEqual(str(cm.exception), message)

    def test_can_be_raised_without_message(self):
        with self.assertRaises(SessionNotFoundError):
            raise SessionNotFoundError()


if __name__ == '__main__':
    unittest.main()
