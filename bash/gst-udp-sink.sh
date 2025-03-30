#! /bin/bash
if [ $# -ne 1 ]; then
    echo "Usage: $0 PORT"
    exit 1
fi

PORT="$1"
DECODER_THREADS=2
SIZEBUFFERS=5
SIZETIME=50000000

gst-launch-1.0 udpsrc port=$PORT caps="video/x-h264, stream-format=(string)byte-stream" ! \
  queue max-size-buffers=$SIZEBUFFERS max-size-time=$SIZETIME leaky=downstream ! \
  h264parse ! \
  avdec_h264 max-threads=$DECODER_THREADS ! \
  videoconvert ! \
  autovideosink sync=false
