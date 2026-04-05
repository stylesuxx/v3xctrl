import struct
import unittest

from src.v3xctrl_helper.sei import (
    SEI_PAYLOAD_SIZE,
    SEI_TYPE_USER_DATA_UNREGISTERED,
    SEI_UUID,
    START_CODE,
    build_sei_nal,
    parse_sei_nal,
)


class TestBuildSeiNal(unittest.TestCase):
    def test_starts_with_annex_b_start_code(self):
        sei = build_sei_nal(1000)

        self.assertEqual(sei[:4], START_CODE)

    def test_nal_header_is_sei_type(self):
        sei = build_sei_nal(1000)

        nal_header = sei[4]
        nal_type = nal_header & 0x1F
        self.assertEqual(nal_type, 6)

    def test_payload_type_is_user_data_unregistered(self):
        sei = build_sei_nal(1000)

        self.assertEqual(sei[5], SEI_TYPE_USER_DATA_UNREGISTERED)

    def test_payload_size_is_correct(self):
        sei = build_sei_nal(1000)

        self.assertEqual(sei[6], SEI_PAYLOAD_SIZE)

    def test_contains_uuid(self):
        sei = build_sei_nal(1000)

        self.assertEqual(sei[7:23], SEI_UUID)

    def test_contains_timestamp(self):
        sei = build_sei_nal(123456789)

        (timestamp,) = struct.unpack(">q", sei[23:31])
        self.assertEqual(timestamp, 123456789)

    def test_ends_with_rbsp_trailing_bits(self):
        sei = build_sei_nal(1000)

        self.assertEqual(sei[-1], 0x80)

    def test_total_length(self):
        sei = build_sei_nal(1000)

        # 4 (start code) + 1 (NAL header) + 1 (type) + 1 (size) + 16 (UUID) + 8 (timestamp) + 1 (RBSP) = 32
        self.assertEqual(len(sei), 32)

    def test_negative_timestamp(self):
        sei = build_sei_nal(-1000000)

        (timestamp,) = struct.unpack(">q", sei[23:31])
        self.assertEqual(timestamp, -1000000)


class TestParseSeiNal(unittest.TestCase):
    def test_roundtrip(self):
        sei = build_sei_nal(123456789)

        result = parse_sei_nal(sei)

        self.assertIsNotNone(result)
        self.assertEqual(result, 123456789)

    def test_sei_prepended_to_frame_data(self):
        sei = build_sei_nal(999)
        # Simulate frame NAL after SEI
        frame_data = START_CODE + b"\x65" + b"\x00" * 100

        result = parse_sei_nal(sei + frame_data)

        self.assertIsNotNone(result)
        self.assertEqual(result, 999)

    def test_returns_none_for_non_sei_data(self):
        # Just some random H264 frame data
        frame_data = START_CODE + b"\x65" + b"\x00" * 50

        result = parse_sei_nal(frame_data)

        self.assertIsNone(result)

    def test_returns_none_for_wrong_uuid(self):
        # Build SEI with wrong UUID
        wrong_uuid = b"\x00" * 16
        payload = wrong_uuid + struct.pack(">q", 1000)
        sei = START_CODE + bytes([0x06, SEI_TYPE_USER_DATA_UNREGISTERED, SEI_PAYLOAD_SIZE]) + payload + b"\x80"

        result = parse_sei_nal(sei)

        self.assertIsNone(result)

    def test_returns_none_for_empty_data(self):
        result = parse_sei_nal(b"")

        self.assertIsNone(result)

    def test_returns_none_for_truncated_data(self):
        sei = build_sei_nal(1000)

        result = parse_sei_nal(sei[:20])

        self.assertIsNone(result)

    def test_large_values(self):
        ts = 1_740_000_000_000_000  # ~2025 in microseconds

        sei = build_sei_nal(ts)
        result = parse_sei_nal(sei)

        self.assertEqual(result, ts)
