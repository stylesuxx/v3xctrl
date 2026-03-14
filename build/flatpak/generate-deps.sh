#!/usr/bin/env bash
set -euo pipefail

# Generates the python-deps.json file for the Flatpak manifest.
#
# Downloads pre-built wheels for the Flatpak SDK's Python version (3.12)
# and generates a flatpak-builder compatible module definition.
# All wheels are placed in a single module so pip can resolve install order.
# Looks up the correct PyPI download URLs via the PyPI JSON API.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REQUIREMENTS="${REPO_ROOT}/build/requirements/viewer-flatpak.txt"
OUTPUT="${SCRIPT_DIR}/python-deps.json"
TMPDIR="$(mktemp -d)"

trap 'rm -rf "${TMPDIR}"' EXIT

# Python version in org.freedesktop.Sdk//24.08
PYTHON_VERSION="312"

pip download \
  --only-binary :all: \
  --platform manylinux2014_x86_64 \
  --platform manylinux_2_17_x86_64 \
  --platform manylinux_2_28_x86_64 \
  --platform linux_x86_64 \
  --python-version "${PYTHON_VERSION}" \
  --implementation cp \
  --abi "cp${PYTHON_VERSION}" \
  --dest "${TMPDIR}" \
  -r "${REQUIREMENTS}"

python3 - "${TMPDIR}" "${OUTPUT}" <<'PYEOF'
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

download_dir = Path(sys.argv[1])
output_file = Path(sys.argv[2])

def get_pypi_url(filename: str) -> str:
    """Look up the download URL for a wheel file via PyPI JSON API."""
    parts = filename.split("-")
    name = parts[0].replace("_", "-").lower()
    version = parts[1]

    api_url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(api_url) as response:
        data = json.loads(response.read())

    for file_info in data["urls"]:
        if file_info["filename"] == filename:
            return file_info["url"]

    raise ValueError(f"Could not find URL for {filename} on PyPI")

sources = []
filenames = []
for whl in sorted(download_dir.iterdir()):
    if not whl.is_file() or not whl.name.endswith(".whl"):
        continue

    sha256 = hashlib.sha256(whl.read_bytes()).hexdigest()

    print(f"Looking up URL for {whl.name}...")
    url = get_pypi_url(whl.name)

    sources.append({
        "type": "file",
        "url": url,
        "sha256": sha256,
    })
    filenames.append(whl.name)

result = {
    "name": "python-deps",
    "buildsystem": "simple",
    "build-commands": [
        "pip3 install --verbose --exists-action=i --no-index "
        '--find-links="file://${PWD}" --prefix=${FLATPAK_DEST} '
        + " ".join(f'"{f}"' for f in filenames)
        + " --no-build-isolation"
    ],
    "sources": sources,
}

output_file.write_text(json.dumps(result, indent=4) + "\n")
print(f"Generated {output_file} with {len(sources)} packages")
PYEOF

echo "Generated ${OUTPUT}"
