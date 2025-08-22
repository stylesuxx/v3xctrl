import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch

from v3xctrl_helper import Address
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.custom_types import PeerEntry, PortType, Role


class TestPacketRelay(unittest.TestCase):
    def setUp(self):
        self.timeout = 30.0
        self.relay = PacketRelay(self.timeout)

    def test_initialization(self):
        self.assertEqual(self.relay.timeout, self.timeout)
        self.assertEqual(self.relay.relay_map, {})
        self.assertEqual(self.relay.session_to_addresses, {})
        self.assertEqual(self.relay.address_to_session, {})
        self.assertTrue(hasattr(self.relay.lock, '__enter__'))
        self.assertTrue(hasattr(self.relay.lock, '__exit__'))

    def test_update_mapping_incomplete_peers(self):
        peers = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("1.1.1.1", 1111))
            },
            Role.VIEWER: {}
        }

        self.relay.update_mapping("session1", peers)

        self.assertEqual(len(self.relay.relay_map), 0)
        self.assertEqual(len(self.relay.session_to_addresses), 0)
        self.assertEqual(len(self.relay.address_to_session), 0)

    def test_update_mapping_missing_role(self):
        peers = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
            }
        }

        self.relay.update_mapping("session1", peers)

        self.assertEqual(len(self.relay.relay_map), 0)
        self.assertEqual(len(self.relay.session_to_addresses), 0)
        self.assertEqual(len(self.relay.address_to_session), 0)

    def test_update_mapping_missing_port_type(self):
        peers = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("1.1.1.1", 1111))
            },
            Role.VIEWER: {
                PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
            }
        }

        self.relay.update_mapping("session1", peers)

        self.assertEqual(len(self.relay.relay_map), 0)
        self.assertEqual(len(self.relay.session_to_addresses), 0)
        self.assertEqual(len(self.relay.address_to_session), 0)

    def test_update_mapping_complete_peers(self):
        with patch('time.time', return_value=1000.0):
            peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }

            self.relay.update_mapping("session1", peers)

        # Check relay mappings
        self.assertEqual(len(self.relay.relay_map), 4)
        self.assertIn(("1.1.1.1", 1111), self.relay.relay_map)
        self.assertIn(("1.1.1.2", 1112), self.relay.relay_map)
        self.assertIn(("2.2.2.1", 2221), self.relay.relay_map)
        self.assertIn(("2.2.2.2", 2222), self.relay.relay_map)

        # Check bidirectional mappings
        self.assertEqual(self.relay.relay_map[("1.1.1.1", 1111)][0], ("2.2.2.1", 2221))
        self.assertEqual(self.relay.relay_map[("1.1.1.2", 1112)][0], ("2.2.2.2", 2222))
        self.assertEqual(self.relay.relay_map[("2.2.2.1", 2221)][0], ("1.1.1.1", 1111))
        self.assertEqual(self.relay.relay_map[("2.2.2.2", 2222)][0], ("1.1.1.2", 1112))

        # Check session tracking
        expected_addresses = {("1.1.1.1", 1111), ("1.1.1.2", 1112), ("2.2.2.1", 2221), ("2.2.2.2", 2222)}
        self.assertEqual(self.relay.session_to_addresses["session1"], expected_addresses)

        # Check reverse mapping
        for addr in expected_addresses:
            self.assertEqual(self.relay.address_to_session[addr], "session1")

        # Check timestamps
        for addr in self.relay.relay_map:
            self.assertEqual(self.relay.relay_map[addr][1], 1000.0)

    def test_update_mapping_overwrites_existing_session(self):
        with patch('time.time', return_value=1000.0):
            # First mapping
            peers1 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers1)

        with patch('time.time', return_value=2000.0):
            # Second mapping with different viewer addresses for same session
            peers2 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("3.3.3.1", 3331)),
                    PortType.CONTROL: PeerEntry(("3.3.3.2", 3332))
                }
            }
            self.relay.update_mapping("session1", peers2)

        # Should only have 4 mappings (old ones cleaned up)
        self.assertEqual(len(self.relay.relay_map), 4)

        # Check new mappings exist
        self.assertEqual(self.relay.relay_map[("1.1.1.1", 1111)][0], ("3.3.3.1", 3331))
        self.assertEqual(self.relay.relay_map[("1.1.1.2", 1112)][0], ("3.3.3.2", 3332))
        self.assertEqual(self.relay.relay_map[("3.3.3.1", 3331)][0], ("1.1.1.1", 1111))
        self.assertEqual(self.relay.relay_map[("3.3.3.2", 3332)][0], ("1.1.1.2", 1112))

        # Check old viewer addresses are removed
        self.assertNotIn(("2.2.2.1", 2221), self.relay.relay_map)
        self.assertNotIn(("2.2.2.2", 2222), self.relay.relay_map)

        # Check session tracking is updated
        expected_addresses = {("1.1.1.1", 1111), ("1.1.1.2", 1112), ("3.3.3.1", 3331), ("3.3.3.2", 3332)}
        self.assertEqual(self.relay.session_to_addresses["session1"], expected_addresses)

    def test_update_mapping_multiple_sessions(self):
        with patch('time.time', return_value=1000.0):
            # Session 1
            peers1 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers1)

            # Session 2
            peers2 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("3.3.3.1", 3331)),
                    PortType.CONTROL: PeerEntry(("3.3.3.2", 3332))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("4.4.4.1", 4441)),
                    PortType.CONTROL: PeerEntry(("4.4.4.2", 4442))
                }
            }
            self.relay.update_mapping("session2", peers2)

        # Should have 8 mappings total
        self.assertEqual(len(self.relay.relay_map), 8)
        self.assertEqual(len(self.relay.session_to_addresses), 2)
        self.assertEqual(len(self.relay.address_to_session), 8)

        # Check session separation
        session1_addrs = {("1.1.1.1", 1111), ("1.1.1.2", 1112), ("2.2.2.1", 2221), ("2.2.2.2", 2222)}
        session2_addrs = {("3.3.3.1", 3331), ("3.3.3.2", 3332), ("4.4.4.1", 4441), ("4.4.4.2", 4442)}

        self.assertEqual(self.relay.session_to_addresses["session1"], session1_addrs)
        self.assertEqual(self.relay.session_to_addresses["session2"], session2_addrs)

    def test_remove_session(self):
        with patch('time.time', return_value=1000.0):
            # Add two sessions
            peers1 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers1)

            peers2 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("3.3.3.1", 3331)),
                    PortType.CONTROL: PeerEntry(("3.3.3.2", 3332))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("4.4.4.1", 4441)),
                    PortType.CONTROL: PeerEntry(("4.4.4.2", 4442))
                }
            }
            self.relay.update_mapping("session2", peers2)

        # Remove session1
        self.relay.remove_session("session1")

        # Check session1 mappings are gone
        self.assertEqual(len(self.relay.relay_map), 4)
        self.assertNotIn("session1", self.relay.session_to_addresses)
        self.assertEqual(len(self.relay.address_to_session), 4)

        # Check session2 is intact
        self.assertIn("session2", self.relay.session_to_addresses)
        self.assertIn(("3.3.3.1", 3331), self.relay.relay_map)

        # Check session1 addresses are not in reverse mapping
        for addr in [("1.1.1.1", 1111), ("1.1.1.2", 1112), ("2.2.2.1", 2221), ("2.2.2.2", 2222)]:
            self.assertNotIn(addr, self.relay.address_to_session)

    def test_get_session_for_address(self):
        with patch('time.time', return_value=1000.0):
            peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers)

        # Test valid addresses
        self.assertEqual(self.relay.get_session_for_address(("1.1.1.1", 1111)), "session1")
        self.assertEqual(self.relay.get_session_for_address(("2.2.2.2", 2222)), "session1")

        # Test invalid address
        self.assertIsNone(self.relay.get_session_for_address(("9.9.9.9", 9999)))

    def test_forward_packet_no_mapping(self):
        mock_sock = Mock(spec=socket.socket)

        self.relay.forward_packet(mock_sock, b"test_data", ("1.1.1.1", 1111))

        mock_sock.sendto.assert_not_called()

    def test_forward_packet_with_mapping(self):
        mock_sock = Mock(spec=socket.socket)

        with patch('time.time', return_value=1000.0):
            # Set up mapping
            self.relay.relay_map[("1.1.1.1", 1111)] = (("2.2.2.2", 2222), 500.0)

        with patch('time.time', return_value=1000.0):
            self.relay.forward_packet(mock_sock, b"test_data", ("1.1.1.1", 1111))

        mock_sock.sendto.assert_called_once_with(b"test_data", ("2.2.2.2", 2222))

        # Check timestamp was updated
        self.assertEqual(self.relay.relay_map[("1.1.1.1", 1111)][1], 1000.0)

    def test_forward_packet_updates_timestamp(self):
        mock_sock = Mock(spec=socket.socket)

        with patch('time.time', return_value=1000.0):
            self.relay.relay_map[("1.1.1.1", 1111)] = (("2.2.2.2", 2222), 500.0)

        with patch('time.time', return_value=1500.0):
            self.relay.forward_packet(mock_sock, b"test_data", ("1.1.1.1", 1111))

        target, timestamp = self.relay.relay_map[("1.1.1.1", 1111)]
        self.assertEqual(target, ("2.2.2.2", 2222))
        self.assertEqual(timestamp, 1500.0)

    def test_forward_packet_multiple_mappings(self):
        mock_sock = Mock(spec=socket.socket)

        self.relay.relay_map[("1.1.1.1", 1111)] = (("2.2.2.1", 2221), 1000.0)
        self.relay.relay_map[("1.1.1.2", 1112)] = (("2.2.2.2", 2222), 1000.0)

        self.relay.forward_packet(mock_sock, b"video_data", ("1.1.1.1", 1111))
        self.relay.forward_packet(mock_sock, b"control_data", ("1.1.1.2", 1112))

        expected_calls = [
            ((b"video_data", ("2.2.2.1", 2221)),),
            ((b"control_data", ("2.2.2.2", 2222)),)
        ]
        self.assertEqual(mock_sock.sendto.call_args_list, expected_calls)

    def test_forward_packet_thread_safety(self):
        mock_sock = Mock(spec=socket.socket)

        # Set up multiple mappings
        for i in range(5):
            self.relay.relay_map[(f"1.1.1.{i}", 1000 + i)] = ((f"2.2.2.{i}", 2000 + i), 1000.0)

        results = []
        errors = []

        def forward_worker(worker_id):
            try:
                addr = (f"1.1.1.{worker_id}", 1000 + worker_id)
                self.relay.forward_packet(mock_sock, f"data_{worker_id}".encode(), addr)
                results.append(worker_id)
            except Exception as e:
                errors.append((worker_id, e))

        threads = []
        for i in range(5):
            thread = threading.Thread(target=forward_worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 5)
        self.assertEqual(mock_sock.sendto.call_count, 5)

    def test_cleanup_expired_mappings_no_mappings(self):
        expired_sessions = self.relay.cleanup_expired_mappings()

        self.assertEqual(len(self.relay.relay_map), 0)
        self.assertEqual(len(expired_sessions), 0)

    def test_cleanup_expired_mappings_no_expired(self):
        with patch('time.time', return_value=1000.0):
            peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers)

        with patch('time.time', return_value=1020.0):  # 20s later - not expired
            expired_sessions = self.relay.cleanup_expired_mappings()

        self.assertEqual(len(self.relay.relay_map), 4)
        self.assertEqual(len(expired_sessions), 0)
        self.assertIn("session1", self.relay.session_to_addresses)

    def test_cleanup_expired_mappings_all_mappings_expired(self):
        with patch('time.time', return_value=1000.0):
            peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers)

        with patch('time.time', return_value=1040.0):  # 40s later - all expired
            expired_sessions = self.relay.cleanup_expired_mappings()

        self.assertEqual(len(self.relay.relay_map), 0)
        self.assertEqual(expired_sessions, {"session1"})
        self.assertNotIn("session1", self.relay.session_to_addresses)

    def test_cleanup_expired_mappings_partial_mappings_expired(self):
        with patch('time.time', return_value=1000.0):
            peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers)

        # Update some mappings to keep them fresh
        with patch('time.time', return_value=1020.0):
            mock_sock = Mock()
            self.relay.forward_packet(mock_sock, b"data", ("1.1.1.1", 1111))  # Keep this one fresh
            self.relay.forward_packet(mock_sock, b"data", ("2.2.2.1", 2221))  # Keep this one fresh

        # Cleanup at time when some mappings are expired
        with patch('time.time', return_value=1040.0):
            expired_sessions = self.relay.cleanup_expired_mappings()

        # Some mappings should remain, session should not be fully expired
        self.assertEqual(len(self.relay.relay_map), 2)
        self.assertEqual(len(expired_sessions), 0)  # Session not fully expired
        self.assertIn("session1", self.relay.session_to_addresses)

        # Check that only fresh mappings remain
        self.assertIn(("1.1.1.1", 1111), self.relay.relay_map)
        self.assertIn(("2.2.2.1", 2221), self.relay.relay_map)
        self.assertNotIn(("1.1.1.2", 1112), self.relay.relay_map)
        self.assertNotIn(("2.2.2.2", 2222), self.relay.relay_map)

        # Check session_to_addresses is updated
        expected_addresses = {("1.1.1.1", 1111), ("2.2.2.1", 2221)}
        self.assertEqual(self.relay.session_to_addresses["session1"], expected_addresses)

    def test_cleanup_expired_mappings_multiple_sessions(self):
        with patch('time.time', return_value=1000.0):
            # Session 1
            peers1 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers1)

            # Session 2
            peers2 = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("3.3.3.1", 3331)),
                    PortType.CONTROL: PeerEntry(("3.3.3.2", 3332))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("4.4.4.1", 4441)),
                    PortType.CONTROL: PeerEntry(("4.4.4.2", 4442))
                }
            }
            self.relay.update_mapping("session2", peers2)

        # Keep session2 active by forwarding packets
        with patch('time.time', return_value=1020.0):
            mock_sock = Mock()
            self.relay.forward_packet(mock_sock, b"data", ("3.3.3.1", 3331))
            self.relay.forward_packet(mock_sock, b"data", ("4.4.4.1", 4441))
            self.relay.forward_packet(mock_sock, b"data", ("3.3.3.2", 3332))
            self.relay.forward_packet(mock_sock, b"data", ("4.4.4.2", 4442))

        # Cleanup - session1 should expire, session2 should remain
        with patch('time.time', return_value=1040.0):
            expired_sessions = self.relay.cleanup_expired_mappings()

        self.assertEqual(expired_sessions, {"session1"})
        self.assertEqual(len(self.relay.relay_map), 4)  # Only session2 mappings
        self.assertNotIn("session1", self.relay.session_to_addresses)
        self.assertIn("session2", self.relay.session_to_addresses)

    def test_cleanup_expired_mappings_thread_safety(self):
        # Set up multiple sessions
        with patch('time.time', return_value=1000.0):
            for i in range(5):
                peers = {
                    Role.STREAMER: {
                        PortType.VIDEO: PeerEntry((f"1.1.1.{i}", 1000 + i)),
                        PortType.CONTROL: PeerEntry((f"1.1.2.{i}", 1100 + i))
                    },
                    Role.VIEWER: {
                        PortType.VIDEO: PeerEntry((f"2.2.1.{i}", 2000 + i)),
                        PortType.CONTROL: PeerEntry((f"2.2.2.{i}", 2100 + i))
                    }
                }
                self.relay.update_mapping(f"session{i}", peers)

        results = []
        errors = []

        def cleanup_worker():
            try:
                with patch('time.time', return_value=1040.0):
                    expired = self.relay.cleanup_expired_mappings()
                    results.append(expired)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=cleanup_worker) for _ in range(3)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should have no errors
        self.assertEqual(len(errors), 0)
        # All threads should complete
        self.assertEqual(len(results), 3)

    def test_complex_scenario_update_forward_cleanup(self):
        mock_sock = Mock(spec=socket.socket)

        # Setup initial mapping
        with patch('time.time', return_value=1000.0):
            peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                    PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                    PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
                }
            }
            self.relay.update_mapping("session1", peers)

        # Forward some packets
        with patch('time.time', return_value=1010.0):
            self.relay.forward_packet(mock_sock, b"video1", ("1.1.1.1", 1111))
            self.relay.forward_packet(mock_sock, b"control1", ("2.2.2.2", 2222))

        # Add another session
        with patch('time.time', return_value=1015.0):
            old_peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("9.9.9.1", 9991)),
                    PortType.CONTROL: PeerEntry(("9.9.9.2", 9992))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("8.8.8.1", 8881)),
                    PortType.CONTROL: PeerEntry(("8.8.8.2", 8882))
                }
            }
            self.relay.update_mapping("old_session", old_peers)

        # Cleanup expired mappings - 35 seconds after initial mapping creation
        with patch('time.time', return_value=1035.0):
            expired_sessions = self.relay.cleanup_expired_mappings()

        # Check results:
        # - session1: some mappings updated (1010), age 25s - kept
        #             some mappings old (1000), age 35s - expired
        # - old_session: all mappings (1015), age 20s - kept
        self.assertEqual(len(expired_sessions), 0)  # No sessions fully expired

        # Only the updated mappings from session1 should remain, plus all of old_session
        remaining_addrs = set(self.relay.relay_map.keys())
        self.assertIn(("1.1.1.1", 1111), remaining_addrs)  # Updated, should remain
        self.assertIn(("2.2.2.2", 2222), remaining_addrs)  # Updated, should remain
        self.assertNotIn(("1.1.1.2", 1112), remaining_addrs)  # Not updated, should be expired
        self.assertNotIn(("2.2.2.1", 2221), remaining_addrs)  # Not updated, should be expired

        # old_session should be intact (all mappings < 30s old)
        self.assertIn(("9.9.9.1", 9991), remaining_addrs)
        self.assertIn(("8.8.8.1", 8881), remaining_addrs)

        # Check forwards worked
        expected_calls = [
            ((b"video1", ("2.2.2.1", 2221)),),
            ((b"control1", ("1.1.1.2", 1112)),)
        ]
        self.assertEqual(mock_sock.sendto.call_args_list, expected_calls)

    def test_bidirectional_communication(self):
        mock_sock = Mock(spec=socket.socket)

        # Setup mapping
        with patch('time.time', return_value=1000.0):
            peers = {
                Role.STREAMER: {
                    PortType.VIDEO: PeerEntry(("streamer.ip", 8080)),
                    PortType.CONTROL: PeerEntry(("streamer.ip", 8081))
                },
                Role.VIEWER: {
                    PortType.VIDEO: PeerEntry(("viewer.ip", 9080)),
                    PortType.CONTROL: PeerEntry(("viewer.ip", 9081))
                }
            }
            self.relay.update_mapping("session1", peers)

        # Test bidirectional forwarding
        with patch('time.time', return_value=1010.0):
            # Streamer to viewer
            self.relay.forward_packet(mock_sock, b"stream_data", ("streamer.ip", 8080))
            # Viewer to streamer
            self.relay.forward_packet(mock_sock, b"control_data", ("viewer.ip", 9081))

        expected_calls = [
            ((b"stream_data", ("viewer.ip", 9080)),),
            ((b"control_data", ("streamer.ip", 8081)),)
        ]
        self.assertEqual(mock_sock.sendto.call_args_list, expected_calls)


if __name__ == '__main__':
    unittest.main()
