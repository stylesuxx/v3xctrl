"""
SO_SNDTIMEO configuration for TCP backpressure.

Prevents buffer bloat by bounding how long sendall() can block.
On timeout, sendall raises OSError. Callers treat this as connection-fatal
(partial frame may have been sent, corrupting the stream).

Only affects sends, recv operations on the same socket are unaffected.
"""

import socket
import struct

# How long a stream socket may sit on a full send buffer before the connection
# counts as dead. The timeout is connection-fatal (a half-sent frame corrupts
# the stream), so it has to clear every stall a live link recovers from: a
# saturated LTE uplink was measured at 1.8 s round trip while still delivering.
# Every second here is also a second before a dead link is noticed and the
# reconnect starts, since TCP itself takes minutes to give up with data pending.
STREAM_SEND_TIMEOUT_MS = 5000


def configure_send_timeout(sock: socket.socket, timeout_ms: int) -> None:
    """Set SO_SNDTIMEO on a TCP socket.

    Args:
        sock: A connected TCP socket.
        timeout_ms: Send timeout in milliseconds.
    """
    sec, ms = divmod(timeout_ms, 1000)
    val = struct.pack("ll", sec, ms * 1000)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, val)
