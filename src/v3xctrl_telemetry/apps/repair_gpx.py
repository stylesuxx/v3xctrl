"""
Closes GPX tracks left open when the streamer was killed or lost power.

A clean stop of v3xctrl-control closes tracks by itself; this is only for the abrupt case.
Nothing is deleted - a half-written last point is dropped, every point before it is kept.

Usage:
    python -m v3xctrl_telemetry.apps.repair_gpx [--path /data/recordings] [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path

from v3xctrl_telemetry.GpxWriter import RepairResult, repair_track

logger = logging.getLogger("repair_gpx")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Close GPX tracks left open by a crash or power loss.")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("/data/recordings"),
        help="Directory to scan (default: /data/recordings)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only report what would change")
    args = parser.parse_args(argv)

    if not args.path.is_dir():
        logger.error("Not a directory: %s", args.path)
        return 1

    tracks = sorted(args.path.glob("*.gpx"))
    if not tracks:
        logger.info("No GPX files in %s", args.path)
        return 0

    failed = False
    for track in tracks:
        try:
            result = repair_track(track, dry_run=args.dry_run)
        except OSError as exc:
            logger.error("%s: %s", track.name, exc)
            failed = True
            continue

        if result is RepairResult.UNREPAIRABLE:
            failed = True

        if args.dry_run and result is RepairResult.REPAIRED:
            logger.info("%s: would repair", track.name)
        else:
            logger.info("%s: %s", track.name, result)

    return int(failed)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
