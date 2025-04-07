#! /bin/bash
if [ $# -lt 2 ]; then
    echo "Usage: $0 HOST PORT [--width val] [--height val] [--framerate val] [--bitrate val] [--buffertime val] [--sizebuffers val]"
    exit 1
fi

HOST="$1"
PORT="$2"
shift 2

WIDTH=1280
HEIGHT=720
FRAMERATE=30

BITRATE=1800000
BITRATE_MODE=1

BUFFERTIME=150000000
SIZEBUFFERS=5

BUFFERTIME_UDP=150000000
SIZEBUFFERS_UDP=5

H264_PROFILE=0
H264_LEVEL=31

while [[ $# -gt 0 ]]; do
  case "$1" in
    --width)
      WIDTH="$2"
      shift 2
      ;;
    --height)
      HEIGHT="$2"
      shift 2
      ;;
    --framerate)
      FRAMERATE="$2"
      shift 2
      ;;
    --bitrate)
      BITRATE="$2"
      shift 2
      ;;
    --buffertime)
      BUFFERTIME="$2"
      shift 2
      ;;
    --sizebuffers)
      SIZEBUFFERS="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done


# Encoder:
# - I frames every 30 frames (once per second)
# - IDR frame every 30 frames - this basically means every I frame is and IDR
#   frame, meaning that following frames can only reference this I frame, n
#   previous I frame.
# - B frames are predictive, since we do not know the future, we can explicitly
#   disable them
# - Profile: 0 (baseline) no B-frames no CABAC. Profile 4 has better compression
#   but also intorudces some additional latency (up to 20ms per frame) for a
#   bitrate reduction of about 15%.
# - Level: 31 (high) 1280x720, 30FPS, 14Mbps max
#
# Test Pattern:
# smpte can easily be generate live, other patterns not so much, would probably
# make sense to pre render video with different test patterns. But for a
# continous datastream smpte is fine anyway (just make sure that the CPU - only
# one core is used by videotestsrc - is not maxed out.)
gst-launch-1.0 -v \
  videotestsrc is-live=true pattern=smpte ! \
  "video/x-raw,width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1" ! \
  queue \
    max-size-buffers=${SIZEBUFFERS} \
    max-size-time=${BUFFERTIME} \
    leaky=downstream ! \
  v4l2h264enc extra-controls="controls,\
    repeat_sequence_header=1,\
    video_bitrate=${BITRATE},\
    bitrate_mode=${BITRATE_MODE},\
    video_gop_size=${FRAMERATE},\
    h264_i_frame_period=${FRAMERATE},\
    video_b_frames=0,\
    h264_profile=${H264_PROFILE},\
    h264_level=${H264_LEVEL}" ! \
  "video/x-h264,level=(string)4,profile=(string)high,stream-format=(string)byte-stream" ! \
  rtph264pay config-interval=1 pt=96 ! \
  udpsink host=${HOST} port=${PORT}
