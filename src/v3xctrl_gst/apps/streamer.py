import argparse
import logging
from typing import Dict, Any

from v3xctrl_gst.Streamer import Streamer


def main() -> None:
    """Main entry point for the streamer application."""
    parser = argparse.ArgumentParser(
        description='GStreamer video streaming pipeline'
    )

    # Required arguments
    parser.add_argument('host', help='Destination host')
    parser.add_argument('port', type=int, help='Destination port')
    parser.add_argument('bind_port', type=int, help='Bind port')

    parser.add_argument('--width', type=int, default=1280, help='Video width (default: 1280)')
    parser.add_argument('--height', type=int, default=720, help='Video height (default: 720)')
    parser.add_argument('--framerate', type=int, default=30, help='Framerate (default: 30)')
    parser.add_argument('--bitrate', type=int, default=1800000, help='Bitrate (default: 1800000)')
    parser.add_argument('--buffertime', type=int, default=150000000, help='Buffer time in ns (default: 150000000)')
    parser.add_argument('--sizebuffers', type=int, default=5, help='Size of buffers (default: 5)')
    parser.add_argument('--recording-dir', type=str, default='', help='Directory to save recording')
    parser.add_argument('--test-pattern', action='store_true', help='Use test pattern instead of camera')
    parser.add_argument('--i-frame-period', type=int, default=30, help='I-frame period (default: 30)')
    parser.add_argument('--qp-minimum', type=int, default=20, help='QP minimum (default: 20)')
    parser.add_argument('--qp-maximum', type=int, default=51, help='QP maximum (default: 51)')

    parser.add_argument(
        "--log", default="ERROR",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR)"
    )

    args = parser.parse_args()

    level_name = args.log.upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    settings: Dict[str, Any] = {
        'width': args.width,
        'height': args.height,
        'framerate': args.framerate,
        'bitrate': args.bitrate,
        'buffertime': args.buffertime,
        'sizebuffers': args.sizebuffers,
        'recording_dir': args.recording_dir,
        'test_pattern': args.test_pattern,
        'h264_i_frame_period': args.i_frame_period,
        'h264_minimum_qp_value': args.qp_minimum,
        'h264_maximum_qp_value': args.qp_maximum,
    }

    # Create and run streamer
    streamer: Streamer = Streamer(args.host, args.port, args.bind_port, settings)
    streamer.run()


if __name__ == '__main__':
    main()
