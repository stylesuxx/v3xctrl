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

gst-launch-1.0 -v \
  videotestsrc is-live=true pattern=smpte ! \
  "video/x-raw,width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1" ! \
  queue \
    max-size-buffers=${SIZEBUFFERS} \
    max-size-time=${BUFFERTIME} \
    leaky=downstream ! \
  x264enc tune=zerolatency bitrate=2048 speed-preset=superfast ! \
  rtph264pay config-interval=1 pt=96 ! \
  udpsink host=${HOST} port=${PORT}
