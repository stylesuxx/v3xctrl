#! /bin/bash
if [ $# -lt 2 ]; then
    echo "Usage: $0 HOST PORT [--width val] [--height val] [--framerate val] [--bitrate val] [--buffertime val] [--sizebuffers val]"
    exit 1
fi

HOST="$1"
PORT="$2"
shift 2

WIDTH=1536
HEIGHT=864
BITRATE=3000000
FRAMERATE=30

BUFFERTIME=150000000
SIZEBUFFERS=5

BUFFERTIME_UDP=150000000
SIZEBUFFERS_UDP=5

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

gst-launch-1.0 -v libcamerasrc ! \
  "video/x-raw,width=$WIDTH,height=$HEIGHT,framerate=$FRAMERATE/1,format=NV12,interlace-mode=progressive" ! \
  queue \
    max-size-buffers=$SIZEBUFFERS \
    max-size-time=$BUFFERTIME \
    leaky=downstream ! \
  v4l2h264enc extra-controls="controls,\
    repeat_sequence_header=1,\
    video_bitrate=$BITRATE,\
    bitrate-mode=constant,\
    h264-i-frame-period=30,\
    h264-idr-interval=30,\
    h264-b-frame=0" ! \
  "video/x-h264,level=(string)4,profile=(string)high,stream-format=(string)byte-stream" ! \
  queue \
    max-size-buffers=$SIZEBUFFERS_UDP \
    max-size-time=$BUFFERTIME_UDP \
    leaky=downstream ! \
  udpsink host=$HOST port=$PORT sync=false async=false
