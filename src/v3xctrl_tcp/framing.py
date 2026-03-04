"""
Length-prefixed TCP framing for UDP-over-TCP tunneling.

Each message is framed as:
    [2-byte big-endian length][payload]

Max payload size is 65535 bytes (fits in !H).
"""

import struct
from socket import socket

HEADER_FORMAT = "!H"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD_SIZE = 0xFFFF


def send_message(sock: socket, data: bytes) -> bool:
    """Send a length-prefixed message. Returns False on error."""
    length = len(data)
    if length > MAX_PAYLOAD_SIZE:
        return False

    header = struct.pack(HEADER_FORMAT, length)
    try:
        sock.sendall(header + data)
        return True

    except OSError:
        return False


def _recv_exact(sock: socket, n: int) -> bytes | None:
    """Read exactly n bytes from socket. Returns None on disconnect."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None

        buf.extend(chunk)

    return bytes(buf)


def recv_message(sock: socket) -> bytes | None:
    """Read a length-prefixed message. Returns None on disconnect."""
    header = _recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None

    (length,) = struct.unpack(HEADER_FORMAT, header)
    if length == 0:
        return b""

    return _recv_exact(sock, length)
