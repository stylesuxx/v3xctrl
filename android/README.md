# v3xctrl Android Viewer

Android application for viewing video streams from the RC car using GStreamer.

## Prerequisites

- Android Studio (or just the Android SDK command line tools)
- Android SDK (API 24+)
- Android NDK 25.x
- GStreamer Android SDK 1.28+

## Setup

### 1. Install Android SDK and NDK

Download and install the Android SDK. You can use Android Studio or the command line tools.

Install the NDK (version 25.x recommended):
```bash
# Via SDK Manager
sdkmanager "ndk;25.2.9519653"

# Or download manually from:
# https://developer.android.com/ndk/downloads
```

### 2. Download GStreamer Android SDK

Download the GStreamer Android SDK (1.28+) from:
https://gstreamer.freedesktop.org/download/

Look for the "Android universal" package (e.g., `gstreamer-1.0-android-universal-1.28.0.tar.xz`).

Extract it to a local directory (e.g., `/home/user/android-gst`):
```bash
mkdir -p ~/android-gst
tar -xf gstreamer-1.0-android-universal-*.tar.xz -C ~/android-gst --strip-components=1
```

The directory structure should look like:
```
android-gst/
├── arm64/
├── armv7/
├── x86/
└── x86_64/
```

Each architecture folder contains `lib/`, `include/`, and `share/` directories.

### 3. Configure local.properties

Create or update `local.properties` in the android folder:

```properties
sdk.dir=/path/to/your/android-sdk
gst.dir=/path/to/your/android-gst
```

Example:
```properties
sdk.dir=/home/user/android-sdk
gst.dir=/home/user/android-gst
```

### 4. Build and Run

The native GStreamer libraries are built automatically by Gradle. A custom `buildNativeLibs` task in `app/build.gradle.kts` handles:
- Running ndk-build for all architectures (arm64-v8a, armeabi-v7a, x86_64)
- Copying built `.so` files to `src/main/jniLibs/`
- Copying `libc++_shared.so` from the NDK sysroot

Simply run:

```bash
cd /path/to/android
./gradlew installDebug
```

Or open the project in Android Studio and run from there.

**Note:** The first build takes longer due to the native GStreamer compilation. Subsequent builds are incremental.

There is also a standalone `build-native.sh` script if you need to rebuild the native libraries outside of Gradle.

## Project Structure

```
android/
├── app/
│   ├── build.gradle.kts                  # App build config (includes native build task)
│   └── src/main/
│       ├── java/com/v3xctrl/viewer/
│       │   ├── MainActivity.kt           # Main activity with navigation
│       │   ├── GstViewer.kt              # JNI wrapper for GStreamer
│       │   ├── control/
│       │   │   ├── UDPReceiver.kt        # UDP message handling & latency loop
│       │   │   ├── UDPTransmitter.kt     # UDP message sending
│       │   │   └── ViewerState.kt        # Observable state (latency, telemetry)
│       │   ├── data/
│       │   │   └── SettingsDataStore.kt  # Persisted settings (DataStore)
│       │   ├── messages/                 # Msgpack message types
│       │   │   ├── Message.kt            # Base class with serialization
│       │   │   ├── Command.kt            # Command with ID tracking
│       │   │   ├── CommandAck.kt         # Command acknowledgment
│       │   │   ├── Commands.kt           # Factory for common commands
│       │   │   ├── Latency.kt            # RTT measurement
│       │   │   └── ...                   # Syn, Ack, Heartbeat, Telemetry, etc.
│       │   ├── relay/
│       │   │   └── RelayConnection.kt    # Relay server connection
│       │   └── ui/
│       │       ├── screens/
│       │       │   ├── ViewerScreen.kt   # Video viewer with OSD
│       │       │   ├── NetworkScreen.kt  # Network settings
│       │       │   ├── FrequenciesScreen.kt
│       │       │   └── OSDScreen.kt      # OSD widget settings
│       │       └── widgets/
│       │           ├── LatencyIndicator.kt    # Colored latency dot
│       │           ├── RecordingIndicator.kt  # REC badge
│       │           └── PipelineTimer.kt       # HH:MM:SS.mmm timer
│       ├── jni/
│       │   ├── Android.mk               # NDK build configuration
│       │   ├── Application.mk           # NDK application settings
│       │   └── gst_viewer.c             # Native GStreamer pipeline code
│       └── jniLibs/                     # Built native libraries (generated, not in git)
├── build-native.sh                      # Standalone native build script
├── local.properties                     # Local SDK/GStreamer paths (not in git)
└── README.md
```

## Supported Architectures

- arm64-v8a (64-bit ARM)
- armeabi-v7a (32-bit ARM)
- x86_64 (64-bit x86, for emulator)

## Troubleshooting

### Library not found errors

The Gradle build should handle this automatically. If you still get errors, check that `src/main/jniLibs/<abi>/` contains `libgstreamer_android.so`, `libv3xctrl_gst.so`, and `libc++_shared.so`. You can force a rebuild of native libs with:
```bash
./gradlew clean assembleDebug
```

### GStreamer.java class not found

The GStreamer.java file should be copied from the GStreamer SDK to:
`app/src/main/java/org/freedesktop/gstreamer/GStreamer.java`

This is already included in the repository.

### Black screen in viewer

Check logcat for GStreamer errors:
```bash
adb logcat | grep -i gst
```

### NDK version compatibility

GStreamer 1.28 works with NDK 25.x. If you encounter build issues, ensure your NDK version matches the one specified in `app/build.gradle.kts` (`ndkVersion`).

### macOS setup

On macOS, replace `linux-x86_64` with `darwin-x86_64` in the libc++_shared.so copy commands.
