#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/build/tmp/viewer-linux"
OUTPUT_DIR="${REPO_ROOT}/build/tmp"
SRC_DIR="${REPO_ROOT}/src"

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}" "${OUTPUT_DIR}"

# Build executable with PyInstaller
pyinstaller --noconfirm --onedir --windowed \
    --icon="${SRC_DIR}/v3xctrl_ui/assets/images/logo.ico" \
    --add-data "${SRC_DIR}/v3xctrl_ui/assets:assets" \
    --collect-data material_icons \
    --distpath "${BUILD_DIR}/dist" \
    --workpath "${BUILD_DIR}/build" \
    --specpath "${BUILD_DIR}" \
    -n V3XCTRL "${SRC_DIR}/v3xctrl_ui/main.py"

# Download appimagetool
APPIMAGETOOL="${BUILD_DIR}/appimagetool-x86_64.AppImage"
wget -q -O "${APPIMAGETOOL}" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "${APPIMAGETOOL}"

# Create AppImage directory structure
APPDIR="${BUILD_DIR}/AppDir"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

cp -r "${BUILD_DIR}/dist/V3XCTRL" "${APPDIR}/usr/bin/v3xctrl"

cp "${SRC_DIR}/v3xctrl_ui/assets/images/logo.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/v3xctrl.png"
cp "${SRC_DIR}/v3xctrl_ui/assets/images/logo.png" "${APPDIR}/v3xctrl.png"

cat > "${APPDIR}/usr/share/applications/v3xctrl.desktop" <<'EOF'
[Desktop Entry]
Name=V3XCTRL
Exec=v3xctrl
Icon=v3xctrl
Type=Application
Categories=Utility;
EOF

cat > "${APPDIR}/AppRun" <<'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec "${HERE}/usr/bin/v3xctrl/V3XCTRL" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

cp "${APPDIR}/usr/share/applications/v3xctrl.desktop" "${APPDIR}/"

# Build AppImage
ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT_DIR}/v3xctrl-viewer-linux.AppImage"

echo "AppImage created: ${OUTPUT_DIR}/v3xctrl-viewer-linux.AppImage"
