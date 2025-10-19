#! /bin/bash
if [ $# -lt 2 ]; then
    echo "Usage: $0 HOST PORT BIND_PORT [--width val] [--height val] [--framerate val] [--bitrate val] [--buffertime val] [--sizebuffers val] [--recording-dir val] [--test-pattern] [--i-frame-period val]"
    exit 1
fi

HOST="$1"
PORT="$2"
BIND_PORT="$3"
shift 3

WIDTH=1280
HEIGHT=720
FRAMERATE=30

BITRATE=1800000
# Bitrate Mode
# 1 is CBR - constant bitrate
# 0 is VBR - variable bitrate
# constrained VBR might generally be the better option than CBR since it will
# result in smaller packages.
BITRATE_MODE=1

BUFFERTIME=150000000
SIZEBUFFERS=5

BUFFERTIME_UDP=150000000
SIZEBUFFERS_UDP=5

I_FRAME_PERIOD=30
H264_PROFILE=0
H264_LEVEL=31

RECORDING_DIR=""
USE_TEST_PATTERN=0

SIZEBUFFERS_WRITE=30

# Defult is 1400 - you might want to decrease this depending on your mobile
# carrier. Use ping or iperf3 to find out what the limit of your carrier might
# be
MTU=1400

while [[ $# -gt 0 ]]; do
  case "$1" in
    --width) WIDTH="$2"; shift 2 ;;
    --height) HEIGHT="$2"; shift 2 ;;
    --framerate) FRAMERATE="$2"; shift 2 ;;
    --bitrate) BITRATE="$2"; shift 2 ;;
    --recording-dir) RECORDING_DIR="$2"; shift 2 ;;
    --i-frame-period) I_FRAME_PERIOD="$2"; shift 2 ;;
    --buffertime) BUFFERTIME="$2"; shift 2 ;;
    --sizebuffers) SIZEBUFFERS="$2"; shift 2 ;;
    --test-pattern) USE_TEST_PATTERN=1; shift ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

TEE_BRANCH=""
if [ -n "$RECORDING_DIR" ]; then
  mkdir -p "$RECORDING_DIR"

  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  FILENAME="$RECORDING_DIR/stream-$TIMESTAMP.ts"

  TEE_BRANCH="t. ! queue leaky=downstream max-size-buffers=$SIZEBUFFERS_WRITE ! h264parse ! mpegtsmux ! filesink sync=false async=false location=$FILENAME"
fi

SOURCE_BRANCH="libcamerasrc"
if [ "$USE_TEST_PATTERN" -eq 1 ]; then
  SOURCE_BRANCH="videotestsrc is-live=true pattern=smpte ! queue ! timeoverlay halignment=center valignment=center"
fi

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
gst-launch-1.0 -v $SOURCE_BRANCH ! \
  "video/x-raw,width=$WIDTH,height=$HEIGHT,framerate=$FRAMERATE/1,format=NV12,interlace-mode=progressive" ! \
  queue \
    max-size-buffers=$SIZEBUFFERS \
    max-size-time=$BUFFERTIME \
    leaky=downstream ! \
  v4l2h264enc extra-controls="controls,\
    repeat_sequence_header=1,\
    video_bitrate=${BITRATE},\
    bitrate_mode=${BITRATE_MODE},\
    video_gop_size=${FRAMERATE},\
    h264_i_frame_period=${I_FRAME_PERIOD},\
    video_b_frames=0,\
    h264_profile=${H264_PROFILE},\
    h264_level=${H264_LEVEL}" ! \
  "video/x-h264,level=(string)4,profile=(string)high,stream-format=(string)byte-stream" ! \
  tee name=t \
    t. ! queue \
      max-size-buffers=$SIZEBUFFERS_UDP \
      max-size-time=$BUFFERTIME_UDP \
      leaky=downstream ! \
    rtph264pay config-interval=1 pt=96 mtu=$MTU ! \
    udpsink host=$HOST port=$PORT bind-port=$BIND_PORT sync=false async=false \
    $TEE_BRANCH
