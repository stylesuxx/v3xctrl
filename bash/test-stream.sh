#! /bin/bash

PORT=6666
FRAMERATE=30

gst-launch-1.0 -v \
  videotestsrc is-live=true pattern=smpte ! \
  video/x-raw,width=1280,height=720,framerate=${FRAMERATE}/1 ! \
  x264enc tune=zerolatency bitrate=2048 speed-preset=superfast ! \
  rtph264pay config-interval=1 pt=96 ! \
  udpsink host=127.0.0.1 port=${PORT}