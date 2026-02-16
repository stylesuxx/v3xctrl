LOCAL_PATH := $(call my-dir)

ifndef GSTREAMER_ROOT_ANDROID
$(error GSTREAMER_ROOT_ANDROID is not defined!)
endif

ifeq ($(TARGET_ARCH_ABI),armeabi-v7a)
GSTREAMER_ROOT := $(GSTREAMER_ROOT_ANDROID)/armv7
else ifeq ($(TARGET_ARCH_ABI),arm64-v8a)
GSTREAMER_ROOT := $(GSTREAMER_ROOT_ANDROID)/arm64
else ifeq ($(TARGET_ARCH_ABI),x86)
GSTREAMER_ROOT := $(GSTREAMER_ROOT_ANDROID)/x86
else ifeq ($(TARGET_ARCH_ABI),x86_64)
GSTREAMER_ROOT := $(GSTREAMER_ROOT_ANDROID)/x86_64
else
$(error Target arch ABI $(TARGET_ARCH_ABI) not supported)
endif

GSTREAMER_NDK_BUILD_PATH := $(GSTREAMER_ROOT)/share/gst-android/ndk-build/

include $(GSTREAMER_NDK_BUILD_PATH)/plugins.mk

# Plugins for video receiver pipeline:
# - coreelements: core elements
# - videoconvertscale: video format conversion
# - opengl: GL rendering (glimagesink)
# - androidmedia: hardware-accelerated Android media codec (amcviddec)
# - udp: UDP source (udpsrc)
# - rtp: RTP depayloaders (rtph264depay)
# - rtpmanager: RTP jitter buffer (rtpjitterbuffer)
# - videoparsersbad: H264 parser (h264parse)
# - libav: Software H264 decoder fallback (avdec_h264)
GSTREAMER_PLUGINS := coreelements videotestsrc videoconvertscale opengl androidmedia udp rtp rtpmanager videoparsersbad libav
GSTREAMER_EXTRA_DEPS := gstreamer-video-1.0 gstreamer-gl-1.0 gstreamer-rtp-1.0

include $(GSTREAMER_NDK_BUILD_PATH)/gstreamer-1.0.mk

include $(CLEAR_VARS)

LOCAL_MODULE    := v3xctrl_gst
LOCAL_SRC_FILES := gst_viewer.c
LOCAL_SHARED_LIBRARIES := gstreamer_android
LOCAL_LDLIBS := -llog -landroid

include $(BUILD_SHARED_LIBRARY)
