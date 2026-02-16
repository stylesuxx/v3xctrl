#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JNI_DIR="$SCRIPT_DIR/app/src/main/jni"
JNILIBS_DIR="$SCRIPT_DIR/app/src/main/jniLibs"

# Read paths from local.properties
if [ -f "$SCRIPT_DIR/local.properties" ]; then
    SDK_DIR=$(grep "^sdk.dir=" "$SCRIPT_DIR/local.properties" | cut -d'=' -f2)
    GST_DIR=$(grep "^gst.dir=" "$SCRIPT_DIR/local.properties" | cut -d'=' -f2)
fi

# Allow environment variables to override
SDK_DIR="${ANDROID_SDK_ROOT:-${SDK_DIR:-$HOME/android-sdk}}"
GST_DIR="${GSTREAMER_ROOT_ANDROID:-${GST_DIR:-$HOME/android-gst}}"

# Find NDK
if [ -n "$ANDROID_NDK_HOME" ]; then
    NDK_DIR="$ANDROID_NDK_HOME"
elif [ -d "$SDK_DIR/ndk" ]; then
    NDK_DIR=$(ls -d "$SDK_DIR/ndk"/*/ 2>/dev/null | head -1 | sed 's:/$::')
fi

if [ -z "$NDK_DIR" ] || [ ! -d "$NDK_DIR" ]; then
    echo "Error: NDK not found. Set ANDROID_NDK_HOME or install NDK via SDK Manager."
    exit 1
fi

if [ ! -d "$GST_DIR" ]; then
    echo "Error: GStreamer SDK not found at $GST_DIR"
    echo "Set gst.dir in local.properties or GSTREAMER_ROOT_ANDROID environment variable."
    exit 1
fi

echo "Using NDK: $NDK_DIR"
echo "Using GStreamer: $GST_DIR"

# Build native libraries
cd "$JNI_DIR"
"$NDK_DIR/ndk-build" \
    NDK_PROJECT_PATH=. \
    APP_BUILD_SCRIPT=./Android.mk \
    NDK_APPLICATION_MK=./Application.mk \
    GSTREAMER_ROOT_ANDROID="$GST_DIR" \
    -j$(nproc)

# Copy to jniLibs
echo "Copying libraries to jniLibs..."
mkdir -p "$JNILIBS_DIR/arm64-v8a" "$JNILIBS_DIR/armeabi-v7a" "$JNILIBS_DIR/x86_64"

cp libs/arm64-v8a/*.so "$JNILIBS_DIR/arm64-v8a/"
cp libs/armeabi-v7a/*.so "$JNILIBS_DIR/armeabi-v7a/"
cp libs/x86_64/*.so "$JNILIBS_DIR/x86_64/"

# Copy libc++_shared.so from NDK
PREBUILT="$NDK_DIR/toolchains/llvm/prebuilt"
if [ -d "$PREBUILT/linux-x86_64" ]; then
    SYSROOT="$PREBUILT/linux-x86_64/sysroot/usr/lib"
elif [ -d "$PREBUILT/darwin-x86_64" ]; then
    SYSROOT="$PREBUILT/darwin-x86_64/sysroot/usr/lib"
else
    echo "Warning: Could not find NDK sysroot for libc++_shared.so"
    exit 0
fi

cp "$SYSROOT/aarch64-linux-android/libc++_shared.so" "$JNILIBS_DIR/arm64-v8a/"
cp "$SYSROOT/arm-linux-androideabi/libc++_shared.so" "$JNILIBS_DIR/armeabi-v7a/"
cp "$SYSROOT/x86_64-linux-android/libc++_shared.so" "$JNILIBS_DIR/x86_64/"

echo "Native build complete!"
