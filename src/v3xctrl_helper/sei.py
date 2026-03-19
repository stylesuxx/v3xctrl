import struct

# v3xctrl SEI UUID - identifies our custom timestamp payloads
SEI_UUID = bytes.fromhex("ef840fbc7f77401886ad83d713d27592")

# Annex B start code
START_CODE = b"\x00\x00\x00\x01"

# NAL header: forbidden_zero_bit=0, nal_ref_idc=0, nal_unit_type=6 (SEI)
NAL_HEADER_SEI = 0x06

# SEI payload type 5: user_data_unregistered
SEI_TYPE_USER_DATA_UNREGISTERED = 0x05

# UUID (16) + timestamp (8) + offset (8)
SEI_PAYLOAD_SIZE = 32


def build_sei_nal(timestamp_us: int, offset_us: int) -> bytes:
    """Build a complete SEI NAL unit with timestamp and NTP offset."""
    payload = SEI_UUID + struct.pack(">qq", timestamp_us, offset_us)

    return (
        START_CODE
        + bytes([NAL_HEADER_SEI, SEI_TYPE_USER_DATA_UNREGISTERED, SEI_PAYLOAD_SIZE])
        + payload
        + b"\x80"  # RBSP trailing bits
    )


def _try_parse_sei(data: bytes, nal_start: int) -> tuple[int, int] | None:
    """Try parsing a SEI NAL at nal_start (pointing to NAL header byte)."""
    if nal_start >= len(data):
        return None

    nal_type = data[nal_start] & 0x1F
    if nal_type != 6:  # Not SEI
        return None

    sei_start = nal_start + 1
    if sei_start + 2 > len(data):
        return None

    payload_type = data[sei_start]
    payload_size = data[sei_start + 1]

    if payload_type != SEI_TYPE_USER_DATA_UNREGISTERED or payload_size != SEI_PAYLOAD_SIZE:
        return None

    uuid_start = sei_start + 2
    uuid_end = uuid_start + 16

    if uuid_end + 16 > len(data):
        return None

    if data[uuid_start:uuid_end] != SEI_UUID:
        return None

    timestamp_us, offset_us = struct.unpack(">qq", data[uuid_end : uuid_end + 16])
    return timestamp_us, offset_us


def parse_sei_nal(data: bytes) -> tuple[int, int] | None:
    """Parse a v3xctrl SEI NAL unit. Returns (timestamp_us, offset_us) or None.

    Supports both Annex B (start code) and AVC (length-prefixed) formats.
    """
    # Try Annex B format (start code delimited)
    pos = 0
    while pos < len(data) - 4:
        if data[pos : pos + 4] == START_CODE:
            result = _try_parse_sei(data, pos + 4)
            if result is not None:
                return result
            pos += 4
        else:
            pos += 1

    # Try AVC format (4-byte length prefix)
    pos = 0
    while pos + 4 < len(data):
        nal_len = struct.unpack(">I", data[pos : pos + 4])[0]
        nal_start = pos + 4

        if nal_len == 0 or nal_start + nal_len > len(data):
            break

        result = _try_parse_sei(data, nal_start)
        if result is not None:
            return result

        pos = nal_start + nal_len

    return None
