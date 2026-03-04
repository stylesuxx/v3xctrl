"""
TCP keepalive configuration for dead connection detection.

Enables SO_KEEPALIVE with aggressive timeouts to detect silently-dead
connections (e.g. mobile carrier NAT timeout without FIN/RST).

With idle=10s, interval=5s, count=3: dead connections detected in ~25s.
"""

import socket

_KEEPIDLE = 10   # Start probes after 10s idle
_KEEPINTVL = 5   # Probe every 5s
_KEEPCNT = 3     # 3 missed probes = dead


def configure_keepalive(sock: socket.socket) -> None:
    """Enable TCP keepalive with aggressive timeouts on a connected socket."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, _KEEPIDLE)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, _KEEPINTVL)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, _KEEPCNT)
