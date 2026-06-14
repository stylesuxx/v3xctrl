"""
Update v3xctrl_repo.json with metadata for a new release image.

Usage:
    # Fetch the latest GitHub release and update
    python update_repo.py

    # Fetch a specific release tag
    python update_repo.py v1.0.0

    # Use a local image file but stamp it with a given tag
    python update_repo.py v1.0.0 --image path/to/v3xctrl-raspios.img.xz

Streams the .xz to compute uncompressed sha256 and size, then prepends a new
subitem to os_list[0].subitems (or replaces an entry that already has the
same name). Validates against schema.json before writing.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import lzma
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_JSON_PATH = SCRIPT_DIR / "v3xctrl_repo.json"
SCHEMA_PATH = SCRIPT_DIR / "schema.json"
GITHUB_REPO = "stylesuxx/v3xctrl"
GITHUB_RELEASE_BASE = f"https://github.com/{GITHUB_REPO}/releases/download"
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"
READ_CHUNK = 1024 * 1024


def fetch_release(tag: str | None) -> dict[str, Any]:
    url = f"{GITHUB_API_BASE}/releases/latest" if tag is None else f"{GITHUB_API_BASE}/releases/tags/{tag}"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request) as response:
        data: dict[str, Any] = json.load(response)

    return data


def find_image_asset(release: dict[str, Any]) -> dict[str, Any]:
    assets: list[dict[str, Any]] = release.get("assets", [])
    for asset in assets:
        if asset["name"].endswith(".img.xz"):
            return asset

    raise RuntimeError(f"No .img.xz asset in release {release.get('tag_name')}")


def download_file(url: str, dest: Path, expected_size: int) -> None:
    request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    with urllib.request.urlopen(request) as response:
        total = int(response.headers.get("Content-Length") or expected_size)
        downloaded = 0
        last_pct = -1
        with dest.open("wb") as f:
            while chunk := response.read(READ_CHUNK):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    if pct != last_pct:
                        print(
                            f"\r  downloading: {pct}% ({downloaded:,}/{total:,} bytes)",
                            end="",
                            flush=True,
                        )
                        last_pct = pct
        if total > 0:
            print()


def hash_and_size_decompressed(xz_path: Path) -> tuple[str, int]:
    sha = hashlib.sha256()
    total = 0
    with lzma.open(xz_path, "rb") as stream:
        while chunk := stream.read(READ_CHUNK):
            sha.update(chunk)
            total += len(chunk)

    return sha.hexdigest(), total


def build_subitem(
    image_path: Path,
    tag: str,
    release_date: str,
    template: dict[str, Any],
) -> dict[str, Any]:
    sha256, extract_size = hash_and_size_decompressed(image_path)
    download_size = image_path.stat().st_size

    item = copy.deepcopy(template)
    item.update(
        {
            "name": f"v3xctrl {tag}",
            "url": f"{GITHUB_RELEASE_BASE}/{tag}/{image_path.name}",
            "extract_size": extract_size,
            "image_download_size": download_size,
            "extract_sha256": sha256,
            "release_date": release_date,
        }
    )

    return item


def upsert_subitem(subitems: list[dict[str, Any]], item: dict[str, Any]) -> str:
    for index, existing in enumerate(subitems):
        if existing.get("name") == item["name"]:
            subitems[index] = item
            return f"replaced existing entry '{item['name']}'"
    subitems.insert(0, item)

    return f"prepended new entry '{item['name']}'"


def validate(repo: dict[str, Any]) -> None:
    with SCHEMA_PATH.open() as f:
        schema = json.load(f)
    jsonschema.validate(instance=repo, schema=schema)


def resolve_image(tag: str | None, image: Path | None) -> tuple[Path, str, str]:
    """
    Returns (image path, tag, release_date YYYY-MM-DD).

    If image is None, downloads from the GitHub release matching tag (or latest).
    """
    if image is not None:
        if tag is None:
            raise SystemExit("--image requires a TAG positional argument")

        if not image.is_file():
            raise SystemExit(f"Image not found: {image}")

        if image.suffix != ".xz":
            raise SystemExit(f"Expected .xz image, got: {image}")

        return image, tag, datetime.now(UTC).strftime("%Y-%m-%d")

    print(f"Fetching release info from GitHub ({tag or 'latest'})...")
    try:
        release = fetch_release(tag)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GitHub API error: {e}") from e

    resolved_tag = release["tag_name"]
    asset = find_image_asset(release)
    download_url = asset["browser_download_url"]
    release_date = release["published_at"][:10]
    dest = Path(tempfile.gettempdir()) / asset["name"]

    if dest.is_file() and dest.stat().st_size == asset["size"]:
        print(f"Using cached {dest}")
    else:
        print(f"Downloading {download_url} -> {dest}")
        download_file(download_url, dest, asset["size"])

    return dest, resolved_tag, release_date


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "tag",
        nargs="?",
        default=None,
        help="Release tag (e.g. v1.0.0). Defaults to the latest GitHub release.",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Use a local .img.xz instead of downloading from the release.",
    )
    args = parser.parse_args()

    image_path, tag, release_date = resolve_image(args.tag, args.image)

    with REPO_JSON_PATH.open() as f:
        repo: dict[str, Any] = json.load(f)

    subitems: list[dict[str, Any]] = repo["os_list"][0]["subitems"]
    if not subitems:
        print("No existing subitem to use as template - add one manually first", file=sys.stderr)
        return 1

    print(f"Hashing {image_path}...")
    new_item = build_subitem(image_path, tag, release_date, subitems[0])
    print(f"  extract_size:        {new_item['extract_size']:,}")
    print(f"  image_download_size: {new_item['image_download_size']:,}")
    print(f"  extract_sha256:      {new_item['extract_sha256']}")
    print(f"  release_date:        {new_item['release_date']}")
    print(f"  url:                 {new_item['url']}")

    action = upsert_subitem(subitems, new_item)
    validate(repo)

    with REPO_JSON_PATH.open("w") as f:
        json.dump(repo, f, indent=2)
        f.write("\n")

    print(f"\n{REPO_JSON_PATH.name}: {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
