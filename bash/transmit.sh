#! /bin/bash
# Gstreamer reference pipeline for sending H264 video stream
# Use for testing on server

HOST="127.0.0.1"
PORT=6666

WIDTH=1280
HEIGHT=720
FRAMERATE=30

gst-launch-1.0 -v \
  videotestsrc is-live=true pattern=smpte ! \
  video/x-raw,width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1 ! \
  x264enc tune=zerolatency bitrate=2048 speed-preset=superfast ! \
  rtph264pay config-interval=1 pt=96 ! \
  udpsink host=${HOST} port=${PORT}
