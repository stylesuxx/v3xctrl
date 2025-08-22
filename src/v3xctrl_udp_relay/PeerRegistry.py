import logging
import threading
from typing import Dict, Set

from v3xctrl_helper import Address

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.custom_types import (
    Role,
    PortType,
    Session,
    PeerEntry,
    RegistrationResult,
    SessionNotFoundError,
)


class PeerRegistry:
    def __init__(self, store: SessionStore, timeout: float) -> None:
        self.store = store
        self.timeout = timeout

        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()

    def register_peer(
        self,
        sid: str,
        role: Role,
        port_type: PortType,
        addr: Address
    ) -> RegistrationResult:
        with self.lock:
            if not self.store.exists(sid):
                return RegistrationResult(
                    error=SessionNotFoundError(f"Session '{sid}' not found")
                )

            session = self.sessions.setdefault(sid, Session())
            is_new_peer = session.register(role, port_type, addr)

            return RegistrationResult(
                is_new_peer=is_new_peer,
                session_ready=session.is_ready()
            )

    def get_session_peers(self, sid: str) -> Dict[Role, Dict[PortType, PeerEntry]]:
        with self.lock:
            session = self.sessions.get(sid)
            if not session:
                return {}

            return session.roles

    def remove_expired_sessions(self, expired_session_ids: Set[str]) -> None:
        with self.lock:
            for sid in expired_session_ids:
                if sid in self.sessions:
                    del self.sessions[sid]
                    logging.info(f"{sid}: Removed expired session")
