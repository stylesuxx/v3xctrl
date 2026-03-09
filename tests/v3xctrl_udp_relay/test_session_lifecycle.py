"""Automated session lifecycle tests across all transport mode combinations.

Tests cover session establishment, peer reconnection, port changes,
timeout behavior, and cleanup for:
- UDP streamer / UDP viewer
- TCP streamer / TCP viewer
- TCP streamer / UDP viewer
- UDP streamer / TCP viewer
"""

import socket
import time
import unittest
from enum import Enum
from unittest.mock import Mock

from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_udp_relay.ForwardTarget import TcpTarget
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.Role import Role
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.custom_types import PortType


class _TransportMode(Enum):
    UDP = "udp"
    TCP = "tcp"


class _SessionLifecycleBase:
    """Base class for session lifecycle tests.

    Subclasses inherit from this AND unittest.TestCase, and set
    streamer_transport and viewer_transport to select the transport
    combination under test.
    """

    streamer_transport: _TransportMode
    viewer_transport: _TransportMode

    TIMEOUT = 450

    def setUp(self):
        self.store = Mock(spec=SessionStore)
        self.store.exists.return_value = True
        self.sock = Mock(spec=socket.socket)
        self.relay = PacketRelay(
            store=self.store,
            sock=self.sock,
            address=("1.2.3.4", 8888),
            timeout=self.TIMEOUT,
        )

        self.streamer_video = ("10.0.0.1", 50000)
        self.streamer_control = ("10.0.0.1", 50001)
        self.viewer_video = ("10.0.0.2", 60000)
        self.viewer_control = ("10.0.0.2", 60001)

        self.tcp_targets: dict[tuple, Mock] = {}

    # -- Helpers --

    def _make_tcp_target(self) -> Mock:
        target = Mock(spec=TcpTarget)
        target.is_alive.return_value = True
        target.send.return_value = True
        return target

    def _register(self, role: str, port_type: str, addr: tuple,
                  transport: _TransportMode) -> None:
        msg = PeerAnnouncement(r=role, i="sid1", p=port_type)
        if transport == _TransportMode.TCP:
            target = self._make_tcp_target()
            self.tcp_targets[addr] = target
            self.relay.register_tcp_peer(msg, addr, target)
        else:
            self.relay.register_peer(msg, addr)

    def _register_streamer(self, video_addr: tuple | None = None,
                           control_addr: tuple | None = None) -> None:
        video = video_addr or self.streamer_video
        control = control_addr or self.streamer_control
        self._register("streamer", "video", video, self.streamer_transport)
        self._register("streamer", "control", control, self.streamer_transport)

    def _register_viewer(self, video_addr: tuple | None = None,
                         control_addr: tuple | None = None) -> None:
        video = video_addr or self.viewer_video
        control = control_addr or self.viewer_control
        self._register("viewer", "video", video, self.viewer_transport)
        self._register("viewer", "control", control, self.viewer_transport)

    def _establish_session(self) -> None:
        self._register_streamer()
        self._register_viewer()

    def _forward_and_complete(self, data: bytes, addr: tuple) -> list | None:
        deferred = self.relay.forward_packet(data, addr)
        if deferred:
            for tcp_target in deferred:
                tcp_target.send(data)
        return deferred

    def _get_role_timeout(self, role: Role) -> float:
        now = time.time()
        session = self.relay.sessions.get("sid1")
        if not session:
            return 0
        port_dict = session.roles.get(role, {})
        max_remaining = 0.0
        with self.relay.mapping_lock:
            for peer_entry in port_dict.values():
                mapping = self.relay.mappings.get(peer_entry.addr)
                if mapping:
                    remaining = self.TIMEOUT - (now - mapping.timestamp)
                    if remaining > max_remaining:
                        max_remaining = remaining
        return max(max_remaining, 0)

    def _disconnect_tcp(self, *addrs: tuple) -> None:
        for addr in addrs:
            target = self.tcp_targets.get(addr)
            if target:
                target.is_alive.return_value = False

    def _set_mapping_timestamp(self, addr: tuple, timestamp: float) -> None:
        with self.relay.mapping_lock:
            mapping = self.relay.mappings.get(addr)
            if mapping:
                mapping.timestamp = timestamp

    def _expire_role_mappings(self, role: Role) -> None:
        session = self.relay.sessions.get("sid1")
        if not session:
            return
        old_time = time.time() - self.TIMEOUT - 1
        for peer_entry in session.roles.get(role, {}).values():
            self._set_mapping_timestamp(peer_entry.addr, old_time)

    def _expire_session(self) -> None:
        session = self.relay.sessions.get("sid1")
        if not session:
            return
        session.last_announcement_at = time.time() - self.TIMEOUT - 1
        self._expire_role_mappings(Role.STREAMER)
        self._expire_role_mappings(Role.VIEWER)

    def assertSessionReady(self) -> None:
        session = self.relay.sessions.get("sid1")
        self.assertIsNotNone(session, "Session should exist")
        self.assertTrue(session.is_ready(), "Session should be ready")

    def assertHasMapping(self, addr: tuple) -> None:
        with self.relay.mapping_lock:
            self.assertIn(addr, self.relay.mappings,
                          f"Mapping should exist for {addr}")

    def assertNoMapping(self, addr: tuple) -> None:
        with self.relay.mapping_lock:
            self.assertNotIn(addr, self.relay.mappings,
                             f"Mapping should not exist for {addr}")

    # -- Session establishment --

    def test_session_establishment(self):
        """Both peers register all ports - session ready, mappings created."""
        self._establish_session()
        self.assertSessionReady()
        self.assertHasMapping(self.streamer_video)
        self.assertHasMapping(self.streamer_control)
        self.assertHasMapping(self.viewer_video)
        self.assertHasMapping(self.viewer_control)

    def test_forward_packet_after_establishment(self):
        """Forward packets in both directions after session is ready."""
        self._establish_session()

        deferred = self.relay.forward_packet(b"video_frame", self.streamer_video)
        self.assertIsNotNone(deferred)

        deferred = self.relay.forward_packet(b"control_cmd", self.viewer_control)
        self.assertIsNotNone(deferred)

    # -- Timeout updates --

    def test_timeout_updates_while_connected(self):
        """Traffic from both sides keeps both timeouts near maximum."""
        self._establish_session()

        self._forward_and_complete(b"video", self.streamer_video)
        self._forward_and_complete(b"control", self.viewer_control)

        streamer_timeout = self._get_role_timeout(Role.STREAMER)
        viewer_timeout = self._get_role_timeout(Role.VIEWER)

        self.assertGreater(streamer_timeout, self.TIMEOUT - 5)
        self.assertGreater(viewer_timeout, self.TIMEOUT - 5)

    def test_forward_from_streamer_only_updates_streamer_timestamp(self):
        """forward_packet updates only the source mapping timestamp."""
        self._establish_session()

        old_time = time.time() - 100
        self._set_mapping_timestamp(self.streamer_video, old_time)
        self._set_mapping_timestamp(self.viewer_video, old_time)

        self._forward_and_complete(b"video", self.streamer_video)

        with self.relay.mapping_lock:
            streamer_ts = self.relay.mappings[self.streamer_video].timestamp
            viewer_ts = self.relay.mappings[self.viewer_video].timestamp

        self.assertGreater(streamer_ts, old_time + 50)
        self.assertAlmostEqual(viewer_ts, old_time, delta=1.0)

    def test_reannouncement_preserves_inactive_peer_timeout(self):
        """Streamer re-announcement does not reset viewer timeout."""
        self._establish_session()

        old_time = time.time() - 200
        self._set_mapping_timestamp(self.viewer_video, old_time)
        self._set_mapping_timestamp(self.viewer_control, old_time)

        self._register_streamer()

        with self.relay.mapping_lock:
            viewer_ts = self.relay.mappings[self.viewer_video].timestamp
        self.assertAlmostEqual(viewer_ts, old_time, delta=1.0)

    # -- Peer restart (same ports) --

    def test_viewer_restart_same_ports(self):
        """Viewer re-registers with same ports - session stays ready."""
        self._establish_session()
        self._register_viewer()
        self.assertSessionReady()
        self.assertHasMapping(self.viewer_video)
        self.assertHasMapping(self.viewer_control)

    def test_streamer_restart_same_ports(self):
        """Streamer re-registers with same ports - session stays ready."""
        self._establish_session()
        self._register_streamer()
        self.assertSessionReady()
        self.assertHasMapping(self.streamer_video)
        self.assertHasMapping(self.streamer_control)

    # -- Port changes --

    def test_viewer_port_change(self):
        """Viewer restarts with different ports - mappings updated."""
        self._establish_session()

        new_video = ("10.0.0.2", 60100)
        new_control = ("10.0.0.2", 60101)
        self._register_viewer(video_addr=new_video, control_addr=new_control)

        self.assertSessionReady()
        self.assertNoMapping(self.viewer_video)
        self.assertNoMapping(self.viewer_control)
        self.assertHasMapping(new_video)
        self.assertHasMapping(new_control)
        self.assertHasMapping(self.streamer_video)

        # Forwarding from streamer reaches new viewer address
        with self.relay.mapping_lock:
            targets = self.relay.mappings[self.streamer_video].targets
        self.assertIn(new_video, targets)
        self.assertNotIn(self.viewer_video, targets)

    def test_streamer_port_change(self):
        """Streamer restarts with different ports - mappings updated."""
        self._establish_session()

        new_video = ("10.0.0.1", 50100)
        new_control = ("10.0.0.1", 50101)
        self._register_streamer(video_addr=new_video, control_addr=new_control)

        self.assertSessionReady()
        self.assertNoMapping(self.streamer_video)
        self.assertNoMapping(self.streamer_control)
        self.assertHasMapping(new_video)
        self.assertHasMapping(new_control)
        self.assertHasMapping(self.viewer_video)

        with self.relay.mapping_lock:
            targets = self.relay.mappings[self.viewer_video].targets
        self.assertIn(new_video, targets)
        self.assertNotIn(self.streamer_video, targets)

    # -- Timeout decreases when one peer disconnects --

    def test_viewer_stop_timeout_decreases(self):
        """When viewer stops, viewer timeout drops while streamer stays high."""
        self._establish_session()

        if self.viewer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.viewer_video, self.viewer_control)

        self._expire_role_mappings(Role.VIEWER)
        self._set_mapping_timestamp(self.streamer_video, time.time())
        self._set_mapping_timestamp(self.streamer_control, time.time())

        self.assertEqual(self._get_role_timeout(Role.VIEWER), 0)
        self.assertGreater(self._get_role_timeout(Role.STREAMER), self.TIMEOUT - 5)

    def test_streamer_stop_timeout_decreases(self):
        """When streamer stops, streamer timeout drops while viewer stays high."""
        self._establish_session()

        if self.streamer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.streamer_video, self.streamer_control)

        self._expire_role_mappings(Role.STREAMER)
        self._set_mapping_timestamp(self.viewer_video, time.time())
        self._set_mapping_timestamp(self.viewer_control, time.time())

        self.assertEqual(self._get_role_timeout(Role.STREAMER), 0)
        self.assertGreater(self._get_role_timeout(Role.VIEWER), self.TIMEOUT - 5)

    # -- Cleanup removes expired roles --

    def test_viewer_disconnect_cleanup_removes_role(self):
        """Viewer disconnects, timeout expires, cleanup removes viewer role."""
        self._establish_session()

        if self.viewer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.viewer_video, self.viewer_control)

        session = self.relay.sessions["sid1"]
        session.last_announcement_at = time.time() - self.TIMEOUT - 1
        self._expire_role_mappings(Role.VIEWER)
        self._set_mapping_timestamp(self.streamer_video, time.time())
        self._set_mapping_timestamp(self.streamer_control, time.time())

        self.relay.cleanup_expired_mappings()

        session = self.relay.sessions.get("sid1")
        self.assertIsNotNone(session)
        self.assertEqual(len(session.roles[Role.VIEWER]), 0)
        self.assertEqual(len(session.roles[Role.STREAMER]), len(PortType))
        self.assertNoMapping(self.viewer_video)
        self.assertNoMapping(self.viewer_control)

    def test_streamer_disconnect_cleanup_removes_role(self):
        """Streamer disconnects, timeout expires, cleanup removes streamer role."""
        self._establish_session()

        if self.streamer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.streamer_video, self.streamer_control)

        session = self.relay.sessions["sid1"]
        session.last_announcement_at = time.time() - self.TIMEOUT - 1
        self._expire_role_mappings(Role.STREAMER)
        self._set_mapping_timestamp(self.viewer_video, time.time())
        self._set_mapping_timestamp(self.viewer_control, time.time())

        self.relay.cleanup_expired_mappings()

        session = self.relay.sessions.get("sid1")
        self.assertIsNotNone(session)
        self.assertEqual(len(session.roles[Role.STREAMER]), 0)
        self.assertEqual(len(session.roles[Role.VIEWER]), len(PortType))
        self.assertNoMapping(self.streamer_video)
        self.assertNoMapping(self.streamer_control)

    def test_both_disconnect_cleanup_removes_session(self):
        """Both peers disconnect, session is removed entirely."""
        self._establish_session()

        if self.viewer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.viewer_video, self.viewer_control)
        if self.streamer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.streamer_video, self.streamer_control)

        self._expire_session()
        self.relay.cleanup_expired_mappings()

        self.assertNotIn("sid1", self.relay.sessions)
        self.assertNoMapping(self.streamer_video)
        self.assertNoMapping(self.viewer_video)

    # -- Stop and re-establish --

    def test_viewer_stop_reestablish(self):
        """Viewer times out and re-registers - session re-established."""
        self._establish_session()

        if self.viewer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.viewer_video, self.viewer_control)

        session = self.relay.sessions["sid1"]
        session.last_announcement_at = time.time() - self.TIMEOUT - 1
        self._expire_role_mappings(Role.VIEWER)
        self._set_mapping_timestamp(self.streamer_video, time.time())
        self._set_mapping_timestamp(self.streamer_control, time.time())

        self.relay.cleanup_expired_mappings()

        session = self.relay.sessions.get("sid1")
        self.assertEqual(len(session.roles[Role.VIEWER]), 0)

        self._register_viewer()
        self.assertSessionReady()
        self.assertHasMapping(self.viewer_video)
        self.assertHasMapping(self.viewer_control)

    def test_streamer_stop_reestablish(self):
        """Streamer times out and re-registers - session re-established."""
        self._establish_session()

        if self.streamer_transport == _TransportMode.TCP:
            self._disconnect_tcp(self.streamer_video, self.streamer_control)

        session = self.relay.sessions["sid1"]
        session.last_announcement_at = time.time() - self.TIMEOUT - 1
        self._expire_role_mappings(Role.STREAMER)
        self._set_mapping_timestamp(self.viewer_video, time.time())
        self._set_mapping_timestamp(self.viewer_control, time.time())

        self.relay.cleanup_expired_mappings()

        session = self.relay.sessions.get("sid1")
        self.assertEqual(len(session.roles[Role.STREAMER]), 0)

        self._register_streamer()
        self.assertSessionReady()
        self.assertHasMapping(self.streamer_video)
        self.assertHasMapping(self.streamer_control)

    # -- TCP-specific behavior --

    def test_tcp_dead_target_prevents_udp_fallback(self):
        """Dead TCP target does not fall through to UDP send."""
        if self.viewer_transport != _TransportMode.TCP:
            self.skipTest("Only applies when viewer is TCP")

        self._establish_session()
        self._disconnect_tcp(self.viewer_video)
        self.sock.sendto.reset_mock()

        deferred = self.relay.forward_packet(b"video", self.streamer_video)

        self.assertIsNotNone(deferred)
        self.assertEqual(len(deferred), 0)
        for call_args in self.sock.sendto.call_args_list:
            self.assertNotEqual(
                call_args[0][1], self.viewer_video,
                "Dead TCP target should not fall back to UDP"
            )

    def test_dead_tcp_target_cleaned_after_mapping_removed(self):
        """Dead TCP target is cleaned up only after its mapping is removed.

        Cleanup checks dead targets before removing expired roles, so it
        takes two cleanup cycles: the first removes the mapping, the second
        removes the dead TCP target.
        """
        if (self.viewer_transport != _TransportMode.TCP and
                self.streamer_transport != _TransportMode.TCP):
            self.skipTest("Only applies when at least one peer is TCP")

        self._establish_session()

        if self.viewer_transport == _TransportMode.TCP:
            tcp_addr = self.viewer_video
            self._disconnect_tcp(self.viewer_video, self.viewer_control)
        else:
            tcp_addr = self.streamer_video
            self._disconnect_tcp(self.streamer_video, self.streamer_control)

        # Dead target should stay because mapping exists
        self.relay.cleanup_expired_mappings()
        self.assertIn(tcp_addr, self.relay.tcp_targets)

        # Expire session so mappings are removed on next cleanup
        self._expire_session()
        self.relay.cleanup_expired_mappings()

        # Mapping removed, but dead target check ran before removal -
        # target still present after this cycle
        self.assertIn(tcp_addr, self.relay.tcp_targets)

        # Second cleanup cycle: dead target check sees no mapping -> removed
        self.relay.cleanup_expired_mappings()
        self.assertNotIn(tcp_addr, self.relay.tcp_targets)

    def test_forwarding_after_port_change(self):
        """Forwarding works correctly after viewer port change."""
        self._establish_session()

        new_video = ("10.0.0.2", 60100)
        new_control = ("10.0.0.2", 60101)
        self._register_viewer(video_addr=new_video, control_addr=new_control)

        # Forward from streamer should succeed
        deferred = self.relay.forward_packet(b"video", self.streamer_video)
        self.assertIsNotNone(deferred)

        # Forward from old viewer address should fail (no mapping)
        deferred = self.relay.forward_packet(b"cmd", self.viewer_control)
        self.assertIsNone(deferred)

        # Forward from new viewer address should succeed
        deferred = self.relay.forward_packet(b"cmd", new_control)
        self.assertIsNotNone(deferred)


class TestSessionLifecycleUDP(_SessionLifecycleBase, unittest.TestCase):
    """UDP streamer, UDP viewer."""
    streamer_transport = _TransportMode.UDP
    viewer_transport = _TransportMode.UDP


class TestSessionLifecycleTCP(_SessionLifecycleBase, unittest.TestCase):
    """TCP streamer, TCP viewer."""
    streamer_transport = _TransportMode.TCP
    viewer_transport = _TransportMode.TCP


class TestSessionLifecycleTCPStreamerUDPViewer(_SessionLifecycleBase, unittest.TestCase):
    """TCP streamer, UDP viewer."""
    streamer_transport = _TransportMode.TCP
    viewer_transport = _TransportMode.UDP


class TestSessionLifecycleUDPStreamerTCPViewer(_SessionLifecycleBase, unittest.TestCase):
    """UDP streamer, TCP viewer."""
    streamer_transport = _TransportMode.UDP
    viewer_transport = _TransportMode.TCP


# ---------------------------------------------------------------------------
# Protocol switching: peer reconnects using a different transport
# ---------------------------------------------------------------------------

class _ProtocolSwitchBase:
    """Helpers for protocol switch tests. Mixed with unittest.TestCase."""

    TIMEOUT = 450

    def setUp(self):
        self.store = Mock(spec=SessionStore)
        self.store.exists.return_value = True
        self.sock = Mock(spec=socket.socket)
        self.relay = PacketRelay(
            store=self.store,
            sock=self.sock,
            address=("1.2.3.4", 8888),
            timeout=self.TIMEOUT,
        )
        self.tcp_targets: dict[tuple, Mock] = {}

        self.streamer_video = ("10.0.0.1", 50000)
        self.streamer_control = ("10.0.0.1", 50001)
        self.viewer_video = ("10.0.0.2", 60000)
        self.viewer_control = ("10.0.0.2", 60001)

    def _make_tcp_target(self) -> Mock:
        target = Mock(spec=TcpTarget)
        target.is_alive.return_value = True
        target.send.return_value = True
        return target

    def _register(self, role: str, port_type: str, addr: tuple,
                  transport: _TransportMode) -> None:
        msg = PeerAnnouncement(r=role, i="sid1", p=port_type)
        if transport == _TransportMode.TCP:
            target = self._make_tcp_target()
            self.tcp_targets[addr] = target
            self.relay.register_tcp_peer(msg, addr, target)
        else:
            self.relay.register_peer(msg, addr)

    def _register_role(self, role: str, video: tuple, control: tuple,
                       transport: _TransportMode) -> None:
        self._register(role, "video", video, transport)
        self._register(role, "control", control, transport)


class TestViewerProtocolSwitch(_ProtocolSwitchBase, unittest.TestCase):

    def test_viewer_switches_udp_to_tcp(self):
        """Viewer initially UDP, reconnects via TCP - session stays ready."""
        self._register_role("streamer", self.streamer_video,
                            self.streamer_control, _TransportMode.UDP)
        self._register_role("viewer", self.viewer_video,
                            self.viewer_control, _TransportMode.UDP)

        session = self.relay.sessions["sid1"]
        self.assertTrue(session.is_ready())

        # Viewer reconnects via TCP
        self._register_role("viewer", self.viewer_video,
                            self.viewer_control, _TransportMode.TCP)

        self.assertTrue(session.is_ready())
        self.assertIn(self.viewer_video, self.relay.mappings)

        # Forward from streamer should produce deferred TCP send
        deferred = self.relay.forward_packet(b"video", self.streamer_video)
        self.assertIsNotNone(deferred)
        self.assertEqual(len(deferred), 1)

    def test_viewer_switches_tcp_to_udp(self):
        """Viewer initially TCP, reconnects via UDP with new ports."""
        self._register_role("streamer", self.streamer_video,
                            self.streamer_control, _TransportMode.UDP)
        self._register_role("viewer", self.viewer_video,
                            self.viewer_control, _TransportMode.TCP)

        session = self.relay.sessions["sid1"]
        self.assertTrue(session.is_ready())

        for addr in (self.viewer_video, self.viewer_control):
            self.tcp_targets[addr].is_alive.return_value = False

        # Viewer reconnects via UDP (new socket -> new ports)
        new_video = ("10.0.0.2", 60100)
        new_control = ("10.0.0.2", 60101)
        self._register_role("viewer", new_video, new_control,
                            _TransportMode.UDP)

        self.assertTrue(session.is_ready())
        self.assertIn(new_video, self.relay.mappings)

        # Forward from streamer should send inline via UDP (no deferred)
        self.sock.sendto.reset_mock()
        deferred = self.relay.forward_packet(b"video", self.streamer_video)
        self.assertIsNotNone(deferred)
        self.assertEqual(len(deferred), 0)
        self.sock.sendto.assert_called_with(b"video", new_video)


class TestStreamerProtocolSwitch(_ProtocolSwitchBase, unittest.TestCase):

    def test_streamer_switches_udp_to_tcp(self):
        """Streamer initially UDP, reconnects via TCP - session stays ready."""
        self._register_role("streamer", self.streamer_video,
                            self.streamer_control, _TransportMode.UDP)
        self._register_role("viewer", self.viewer_video,
                            self.viewer_control, _TransportMode.UDP)

        session = self.relay.sessions["sid1"]
        self.assertTrue(session.is_ready())

        # Streamer reconnects via TCP
        self._register_role("streamer", self.streamer_video,
                            self.streamer_control, _TransportMode.TCP)

        self.assertTrue(session.is_ready())
        self.assertIn(self.streamer_video, self.relay.mappings)

        # Forward from viewer to streamer should produce deferred TCP send
        deferred = self.relay.forward_packet(b"control", self.viewer_control)
        self.assertIsNotNone(deferred)
        self.assertEqual(len(deferred), 1)

    def test_streamer_switches_tcp_to_udp(self):
        """Streamer initially TCP, reconnects via UDP with new ports."""
        self._register_role("streamer", self.streamer_video,
                            self.streamer_control, _TransportMode.TCP)
        self._register_role("viewer", self.viewer_video,
                            self.viewer_control, _TransportMode.UDP)

        session = self.relay.sessions["sid1"]
        self.assertTrue(session.is_ready())

        for addr in (self.streamer_video, self.streamer_control):
            self.tcp_targets[addr].is_alive.return_value = False

        # Streamer reconnects via UDP (new socket -> new ports)
        new_video = ("10.0.0.1", 50100)
        new_control = ("10.0.0.1", 50101)
        self._register_role("streamer", new_video, new_control,
                            _TransportMode.UDP)

        self.assertTrue(session.is_ready())

        # Forward from viewer to streamer should go inline via UDP
        self.sock.sendto.reset_mock()
        deferred = self.relay.forward_packet(b"control", self.viewer_control)
        self.assertIsNotNone(deferred)
        self.assertEqual(len(deferred), 0)
        self.sock.sendto.assert_called_with(b"control", new_control)


# ---------------------------------------------------------------------------
# Spectator: all transport combinations for spectator + streamer
# ---------------------------------------------------------------------------

class _SpectatorBase:
    """Helpers for spectator tests. Mixed with unittest.TestCase."""

    TIMEOUT = 450

    def setUp(self):
        self.store = Mock(spec=SessionStore)
        self.store.exists.return_value = True
        self.store.get_session_id_from_spectator_id.return_value = "sid1"
        self.sock = Mock(spec=socket.socket)
        self.relay = PacketRelay(
            store=self.store,
            sock=self.sock,
            address=("1.2.3.4", 8888),
            timeout=self.TIMEOUT,
        )
        self.tcp_targets: dict[tuple, Mock] = {}

        self.streamer_video = ("10.0.0.1", 50000)
        self.streamer_control = ("10.0.0.1", 50001)
        self.viewer_video = ("10.0.0.2", 60000)
        self.viewer_control = ("10.0.0.2", 60001)
        self.spectator_video = ("10.0.0.3", 70000)
        self.spectator_control = ("10.0.0.3", 70001)

    def _make_tcp_target(self) -> Mock:
        target = Mock(spec=TcpTarget)
        target.is_alive.return_value = True
        target.send.return_value = True
        return target

    def _register(self, role: str, port_type: str, addr: tuple,
                  transport: _TransportMode) -> None:
        msg = PeerAnnouncement(r=role, i="sid1", p=port_type)
        if transport == _TransportMode.TCP:
            target = self._make_tcp_target()
            self.tcp_targets[addr] = target
            self.relay.register_tcp_peer(msg, addr, target)
        else:
            self.relay.register_peer(msg, addr)

    def _register_role(self, role: str, video: tuple, control: tuple,
                       transport: _TransportMode) -> None:
        self._register(role, "video", video, transport)
        self._register(role, "control", control, transport)

    def _establish_session(self, streamer_transport: _TransportMode,
                           viewer_transport: _TransportMode) -> None:
        self._register_role("streamer", self.streamer_video,
                            self.streamer_control, streamer_transport)
        self._register_role("viewer", self.viewer_video,
                            self.viewer_control, viewer_transport)

    def _register_spectator(self, transport: _TransportMode) -> None:
        self._register("spectator", "video", self.spectator_video, transport)
        self._register("spectator", "control", self.spectator_control, transport)

    def _assert_spectator_in_streamer_targets(self) -> None:
        with self.relay.mapping_lock:
            video_targets = self.relay.mappings[self.streamer_video].targets
            control_targets = self.relay.mappings[self.streamer_control].targets
        self.assertIn(self.spectator_video, video_targets)
        self.assertIn(self.spectator_control, control_targets)

    def _assert_spectator_receives_data(self,
                                        spectator_transport: _TransportMode) -> None:
        self.sock.sendto.reset_mock()
        for addr in list(self.tcp_targets.values()):
            addr.send.reset_mock()

        deferred = self.relay.forward_packet(b"video_frame", self.streamer_video)
        self.assertIsNotNone(deferred)
        if deferred:
            for tcp_target in deferred:
                tcp_target.send(b"video_frame")

        if spectator_transport == _TransportMode.UDP:
            send_addrs = [c[0][1] for c in self.sock.sendto.call_args_list]
            self.assertIn(self.spectator_video, send_addrs)
        else:
            spectator_target = self.tcp_targets[self.spectator_video]
            spectator_target.send.assert_called_with(b"video_frame")


class TestSpectatorUDPWithStreamerUDP(_SpectatorBase, unittest.TestCase):

    def test_spectator_joins_and_receives(self):
        """UDP spectator joins session with UDP streamer."""
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.UDP)

        self._assert_spectator_in_streamer_targets()
        self._assert_spectator_receives_data(_TransportMode.UDP)


class TestSpectatorTCPWithStreamerUDP(_SpectatorBase, unittest.TestCase):

    def test_spectator_joins_and_receives(self):
        """TCP spectator joins session with UDP streamer."""
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.TCP)

        self._assert_spectator_in_streamer_targets()
        self._assert_spectator_receives_data(_TransportMode.TCP)


class TestSpectatorUDPWithStreamerTCP(_SpectatorBase, unittest.TestCase):

    def test_spectator_joins_and_receives(self):
        """UDP spectator joins session with TCP streamer."""
        self._establish_session(_TransportMode.TCP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.UDP)

        self._assert_spectator_in_streamer_targets()
        self._assert_spectator_receives_data(_TransportMode.UDP)


class TestSpectatorTCPWithStreamerTCP(_SpectatorBase, unittest.TestCase):

    def test_spectator_joins_and_receives(self):
        """TCP spectator joins session with TCP streamer."""
        self._establish_session(_TransportMode.TCP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.TCP)

        self._assert_spectator_in_streamer_targets()
        self._assert_spectator_receives_data(_TransportMode.TCP)


class TestSpectatorJoinsBeforeSessionReady(_SpectatorBase, unittest.TestCase):
    """Test spectators that register before the session is ready."""

    def test_tcp_spectator_gets_peer_info_when_session_becomes_ready(self):
        """TCP spectator that joins before session is ready gets PeerInfo when session becomes ready."""
        # Spectator joins first (session not ready yet)
        self._register_spectator(_TransportMode.TCP)

        session = self.relay.sessions.get("sid1")
        self.assertIsNotNone(session)
        self.assertFalse(session.is_ready())

        # PeerInfo should NOT have been sent yet (only on register since session not ready)
        spectator_video_target = self.tcp_targets[self.spectator_video]
        spectator_control_target = self.tcp_targets[self.spectator_control]
        spectator_video_target.send.assert_not_called()
        spectator_control_target.send.assert_not_called()

        # Now establish the session (streamer + viewer connect)
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)

        # PeerInfo should have been sent to spectator when session became ready
        spectator_video_target.send.assert_called()
        spectator_control_target.send.assert_called()

    def test_udp_spectator_gets_peer_info_when_session_becomes_ready(self):
        """UDP spectator that joins before session is ready gets PeerInfo when session becomes ready."""
        # Spectator joins first
        self._register_spectator(_TransportMode.UDP)

        session = self.relay.sessions.get("sid1")
        self.assertFalse(session.is_ready())

        # No PeerInfo sent via UDP yet for spectator
        video_sends = [c[0][1] for c in self.sock.sendto.call_args_list]
        self.assertNotIn(self.spectator_video, video_sends)

        # Session becomes ready
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)

        # PeerInfo should be sent to spectator addresses
        all_sends = [c[0][1] for c in self.sock.sendto.call_args_list]
        self.assertIn(self.spectator_video, all_sends)
        self.assertIn(self.spectator_control, all_sends)

    def test_spectator_mappings_set_up_when_session_becomes_ready(self):
        """Spectator mappings are set up when the session becomes ready."""
        self._register_spectator(_TransportMode.UDP)
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)

        self._assert_spectator_in_streamer_targets()
        self._assert_spectator_receives_data(_TransportMode.UDP)


class TestSpectatorTransportSwitch(_SpectatorBase, unittest.TestCase):
    """Test spectator switching between UDP and TCP transport."""

    def test_spectator_udp_to_tcp_updates_transport(self):
        """Switching spectator from UDP to TCP updates the transport in the spectator entry."""
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.UDP)

        session = self.relay.sessions["sid1"]
        for peer_entry in session.spectators[0].ports.values():
            self.assertEqual(peer_entry.transport.name, "UDP")

        # Switch to TCP using new addresses (different ports)
        new_spectator_video = ("10.0.0.3", 71000)
        new_spectator_control = ("10.0.0.3", 71001)
        self._register("spectator", "video", new_spectator_video, _TransportMode.TCP)
        self._register("spectator", "control", new_spectator_control, _TransportMode.TCP)

        # Transport should be TCP now
        for peer_entry in session.spectators[0].ports.values():
            self.assertEqual(peer_entry.transport.name, "TCP")

    def test_spectator_udp_to_tcp_cleans_up_old_addresses(self):
        """Switching spectator from UDP to TCP removes old UDP addresses from spectator_by_address."""
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.UDP)

        # Old UDP addresses should be in spectator_by_address
        self.assertIn(self.spectator_video, self.relay.spectator_by_address)
        self.assertIn(self.spectator_control, self.relay.spectator_by_address)

        # Switch to TCP
        new_spectator_video = ("10.0.0.3", 71000)
        new_spectator_control = ("10.0.0.3", 71001)
        self._register("spectator", "video", new_spectator_video, _TransportMode.TCP)
        self._register("spectator", "control", new_spectator_control, _TransportMode.TCP)

        # Old UDP addresses should be removed from spectator_by_address
        self.assertNotIn(self.spectator_video, self.relay.spectator_by_address)
        self.assertNotIn(self.spectator_control, self.relay.spectator_by_address)

        # New TCP addresses should be present
        self.assertIn(new_spectator_video, self.relay.spectator_by_address)
        self.assertIn(new_spectator_control, self.relay.spectator_by_address)

    def test_spectator_udp_to_tcp_cleans_up_old_mapping_targets(self):
        """Switching spectator from UDP to TCP removes old addresses from streamer mapping targets."""
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.UDP)

        # Old UDP addresses should be in streamer mapping targets
        self._assert_spectator_in_streamer_targets()

        # Switch to TCP
        new_spectator_video = ("10.0.0.3", 71000)
        new_spectator_control = ("10.0.0.3", 71001)
        self._register("spectator", "video", new_spectator_video, _TransportMode.TCP)
        self._register("spectator", "control", new_spectator_control, _TransportMode.TCP)

        with self.relay.mapping_lock:
            video_targets = self.relay.mappings[self.streamer_video].targets
            control_targets = self.relay.mappings[self.streamer_control].targets

        # Old UDP addresses should be removed
        self.assertNotIn(self.spectator_video, video_targets)
        self.assertNotIn(self.spectator_control, control_targets)

        # New TCP addresses should be present
        self.assertIn(new_spectator_video, video_targets)
        self.assertIn(new_spectator_control, control_targets)

    def test_spectator_receives_data_after_transport_switch(self):
        """Spectator receives data via TCP after switching from UDP."""
        self._establish_session(_TransportMode.UDP, _TransportMode.UDP)
        self._register_spectator(_TransportMode.UDP)

        # Switch to TCP
        new_spectator_video = ("10.0.0.3", 71000)
        new_spectator_control = ("10.0.0.3", 71001)
        self._register("spectator", "video", new_spectator_video, _TransportMode.TCP)
        self._register("spectator", "control", new_spectator_control, _TransportMode.TCP)

        # Update instance vars for assertion helper
        self.spectator_video = new_spectator_video
        self.spectator_control = new_spectator_control
        self._assert_spectator_receives_data(_TransportMode.TCP)


if __name__ == "__main__":
    unittest.main()
