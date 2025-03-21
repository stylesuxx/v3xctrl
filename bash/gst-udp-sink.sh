#! /bin/bash
if [ $# -ne 1 ]; then
    echo "Usage: $0 PORT"
    exit 1
fi

PORT="$1"
DECODER_THREADS=2

gst-launch-1.0 udpsrc port=$PORT ! \
  application/x-rtp, clock-rate=90000,payload=96 ! \
  queue max-size-buffers=10 max-size-time=100000000 leaky=downstream ! \
  rtph264depay ! \
  video/x-h264 ! \
  h264parse ! \
  avdec_h264 max-threads=$DECODER_THREADS ! \
  queue max-size-buffers=5 leaky=downstream ! \
  videoconvert ! \
  autovideosink sync=false
