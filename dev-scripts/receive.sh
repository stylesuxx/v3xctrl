#! /bin/bash
# Gstreamer reference pipeline for receiving H264 video stream
# Use for testing on server
if [ $# -ne 1 ]; then
    echo "Usage: $0 PORT"
    exit 1
fi

PORT="$1"

DECODER_THREADS=2
SIZEBUFFERS=5
SIZETIME=50000000

gst-launch-1.0 -v \
  udpsrc port=$PORT caps="application/x-rtp, media=video, encoding-name=H264, payload=96, clock-rate=90000" ! \
  rtpjitterbuffer latency=0 drop-on-latency=true ! \
  rtph264depay ! \
  h264parse ! \
  avdec_h264 max-threads=$DECODER_THREADS ! \
  videoconvert ! \
  autovideosink sync=false
