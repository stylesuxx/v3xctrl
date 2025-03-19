#! /bin/bash
HOST="62.178.46.35"
PORT=6666

# NOTE: Eher laggy
BITRATE=5000000
WIDTH=1920
HEIGHT=1080
FRAMERATE=30/1

# NOTE: Nahezu perfekt
WIDTH=1280
HEIGHT=720
BITRATE=3000000
FRAMERATE=30/1
CAMBUFFERTIME=50000000

# NOTE: Sehr matschig - muesste vermutlich mehr bitrate haben.
# WIDTH=1280
# HEIGHT=720
# BITRATE=1500000
# FRAMERATE=60/1

gst-launch-1.0 -v libcamerasrc ! \
  video/x-raw,width=$WIDTH,height=$HEIGHT,framerate=$FRAMERATE,format=NV12,interlace-mode=progressive ! \
  queue max-size-buffers=5 max-size-time=$CAMBUFFERTIME leaky=downstream ! \
  v4l2h264enc extra-controls="controls,repeat_sequence_header=1,video_bitrate=$BITRATE,h264-i-frame-period=30,h264-b-frame=0" ! \
  'video/x-h264,level=(string)4,profile=(string)high' ! \
  h264parse ! \
  rtph264pay config-interval=1 pt=96 mtu=1400 ! \
  udpsink host=$HOST sync=false async=false port=$PORT
