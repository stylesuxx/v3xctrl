import argparse
import logging
from typing import Any

from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_gst.Streamer import Streamer
from v3xctrl_tcp import Transport
from v3xctrl_tcp.TcpTunnel import TcpTunnel


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
    parser.add_argument('--mtu', type=int, default=1400, help='RTP MTU in bytes (default: 1400)')
    parser.add_argument('--h264-profile', type=str, default='high', help='H.264 profile (default: high)')
    parser.add_argument('--buffertime', type=int, default=150000000, help='Buffer time in ns (default: 150000000)')
    parser.add_argument('--sizebuffers', type=int, default=5, help='Size of buffers (default: 5)')
    parser.add_argument('--recording-dir', type=str, default='', help='Directory to save recording')
    parser.add_argument('--test-pattern', action='store_true', default=False, help='Use test pattern instead of camera')
    parser.add_argument('--i-frame-period', type=int, default=30, help='I-frame period (default: 30)')
    parser.add_argument('--qp-minimum', type=int, default=20, help='QP minimum (default: 20)')
    parser.add_argument('--qp-maximum', type=int, default=51, help='QP maximum (default: 51)')
    parser.add_argument('--max-i-frame-bytes', type=int, default=25600, help='Maximum i-frame size (default: 25600)')
    parser.add_argument('--enable-i-frame-adjust', action='store_true', help='Use test pattern instead of camera')
    parser.add_argument('--file-src', type=str, default=None, help='Path to src file')
    parser.add_argument('--af-mode', type=int, default=0, help='Auto focus mode (default: 0 - off)')
    parser.add_argument('--lens-position', type=float, default=0, help='Lens position (default: 0 - infinity)')
    parser.add_argument('--analogue-gain-mode', type=int, default=0, help='Analogue gain mode (default: 0 - auto)')
    parser.add_argument('--analogue-gain', type=int, default=1, help='Analogue gain(default: 1)')
    parser.add_argument('--exposure-time-mode', type=int, default=0, help='Exposure time mode (default: 0 - auto)')
    parser.add_argument('--exposure-time', type=int, default=32000, help='Exposure time in us (default: 32000000)')
    parser.add_argument(
        '--autostart-recording', action='store_true', default=False,
        help='Automatically start recording (requires recording-dir to be set)'
    )
    parser.add_argument('--sensor-mode', type=str, default="0x0", help='Path to src file (dafault: 0x0; automatic)')
    parser.add_argument('--brightness', type=float, default=0.0, help='Brightness (default: 0)')
    parser.add_argument('--contrast', type=float, default=1.0, help='Contrast (default: 1.0)')
    parser.add_argument('--saturation', type=float, default=1.0, help='Saturation (default: 1.0)')
    parser.add_argument('--sharpness', type=float, default=0.0, help='Sharpness (default: 1.0)')

    parser.add_argument(
        "--log", default="ERROR",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR)"
    )
    parser.add_argument(
        '--transport', type=str, default='udp', choices=['udp', 'tcp'],
        help='Transport protocol (default: udp)'
    )
    parser.add_argument(
        '--relay-session-id', type=str, default=None,
        help='Relay session ID (enables relay TCP mode with PeerAnnouncement handshake)'
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

    settings: dict[str, Any] = {
        'width': args.width,
        'height': args.height,
        'framerate': args.framerate,
        'bitrate': args.bitrate,
        'mtu': args.mtu,
        'h264_profile': args.h264_profile,
        'buffertime': args.buffertime,
        'sizebuffers': args.sizebuffers,
        'recording_dir': args.recording_dir,
        'test_pattern': args.test_pattern,
        'h264_i_frame_period': args.i_frame_period,
        'h264_minimum_qp_value': args.qp_minimum,
        'h264_maximum_qp_value': args.qp_maximum,
        'max_i_frame_bytes': args.max_i_frame_bytes,
        'enable_i_frame_adjust': args.enable_i_frame_adjust,
        'file_src': args.file_src,
        'af_mode': args.af_mode,
        'lens_position': args.lens_position,
        'analogue_gain_mode': args.analogue_gain_mode,
        'analogue_gain': args.analogue_gain,
        'exposure_time_mode': args.exposure_time_mode,
        'exposure_time': args.exposure_time,
        'recording': args.autostart_recording,
        'sensor_mode_width': int(args.sensor_mode.split('x')[0]),
        'sensor_mode_height': int(args.sensor_mode.split('x')[1]),
        'brightness': args.brightness,
        'contrast': args.contrast,
        'saturation': args.saturation,
        'sharpness': args.sharpness,
        'timing_enabled': level == logging.DEBUG,
    }

    tcp_tunnel = None
    video_host = args.host
    video_port = args.port

    if args.transport == Transport.TCP:
        handshake = None
        if args.relay_session_id:
            handshake = PeerAnnouncement(
                r="streamer", i=args.relay_session_id, p="video"
            ).to_bytes()

        tcp_tunnel = TcpTunnel(
            remote_host=args.host,
            remote_port=args.port,
            local_component_port=0,
            bidirectional=False,
            handshake=handshake,
        )
        tcp_tunnel.start()
        ephemeral_port = tcp_tunnel.wait_for_port()
        if ephemeral_port is None:
            logging.error("Failed to allocate TCP tunnel port")
            return
        video_host = "127.0.0.1"
        video_port = ephemeral_port
        logging.info(
            f"TCP tunnel: udpsink -> 127.0.0.1:{ephemeral_port} "
            f"-> TCP -> {args.host}:{args.port}"
        )

    streamer: Streamer = Streamer(video_host, video_port, args.bind_port, settings)

    try:
        streamer.run()
    finally:
        if tcp_tunnel:
            tcp_tunnel.stop()


if __name__ == '__main__':
    main()
