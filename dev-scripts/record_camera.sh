#!/bin/bash

WIDTH="${WIDTH:-1280}"
HEIGHT="${HEIGHT:-720}"
FRAMERATE="${FRAMERATE:-30}"
FORMAT="${FORMAT:-NV12}"
DURATION="${DURATION:-60}"  # seconds, 0 for unlimited
OUTPUT_DIR="${OUTPUT_DIR:-/data/recordings}"
MODE="${MODE:-compressed}"  # "raw" or "compressed"

# Generate timestamp for filename
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Record raw camera data from libcamerasrc

OPTIONS:
    -w WIDTH        Video width (default: 1280)
    -h HEIGHT       Video height (default: 720)
    -f FRAMERATE    Framerate (default: 30)
    -d DURATION     Duration in seconds, 0=unlimited (default: 60)
    -o OUTPUT_DIR   Output directory (default: ./camera_recordings)
    -F FORMAT       Pixel format (default: NV12)
    --help          Show this help

EXAMPLES:
    # Record truly raw video (HUGE file!)
    $0 -d 10

    # Record at different resolution
    $0 -w 1920 -h 1080 -f 25

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -w) WIDTH="$2"; shift 2 ;;
        -h) HEIGHT="$2"; shift 2 ;;
        -f) FRAMERATE="$2"; shift 2 ;;
        -d) DURATION="$2"; shift 2 ;;
        -o) OUTPUT_DIR="$2"; shift 2 ;;
        -F) FORMAT="$2"; shift 2 ;;
        --help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

echo "Recording Settings:"
echo "  Resolution: ${WIDTH}x${HEIGHT}"
echo "  Framerate: ${FRAMERATE} fps"
echo "  Format: ${FORMAT}"
echo "  Duration: ${DURATION}s (0=unlimited)"
echo "  Mode: ${MODE}"
echo "  Output: ${OUTPUT_DIR}"
echo ""

OUTPUT_FILE="${OUTPUT_DIR}/camera-raw-${TIMESTAMP}.yuv"

echo "Recording RAW video to: ${OUTPUT_FILE}"
echo ""

if [ "$DURATION" -gt 0 ]; then
    timeout --signal=INT ${DURATION}s gst-launch-1.0 -e \
        libcamerasrc ! \
        video/x-raw,width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1,format=${FORMAT} ! \
        filesink location="${OUTPUT_FILE}"
else
    gst-launch-1.0 -e \
        libcamerasrc ! \
        video/x-raw,width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1,format=${FORMAT} ! \
        filesink location="${OUTPUT_FILE}"
fi

echo ""
echo "Recording complete!"
if [ -f "${OUTPUT_FILE}" ]; then
    echo "File: ${OUTPUT_FILE}"
    echo "Size: $(du -h "${OUTPUT_FILE}" | cut -f1)"
else
    echo "Error: Recording file was not created: ${OUTPUT_FILE}"
    exit 1
fi
