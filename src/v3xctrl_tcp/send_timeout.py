"""
SO_SNDTIMEO configuration for TCP backpressure.

Prevents buffer bloat by bounding how long sendall() can block.
On timeout, sendall raises OSError. Callers treat this as connection-fatal
(partial frame may have been sent, corrupting the stream).

Only affects sends, recv operations on the same socket are unaffected.
"""

import socket
import struct


def configure_send_timeout(sock: socket.socket, timeout_ms: int) -> None:
    """Set SO_SNDTIMEO on a TCP socket.

    Args:
        sock: A connected TCP socket.
        timeout_ms: Send timeout in milliseconds.
    """
    sec, ms = divmod(timeout_ms, 1000)
    val = struct.pack("ll", sec, ms * 1000)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, val)
