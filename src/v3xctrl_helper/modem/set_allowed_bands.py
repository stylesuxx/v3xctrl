import argparse
import logging

from atlib import AIR780EU


def main() -> None:
    parser = argparse.ArgumentParser(description="Set allowed LTE bands on AIR780EU modem.")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
    parser.add_argument("bands", help="Comma-separated list of LTE band integers (e.g. 1,3,7,20)")

    parser.add_argument(
        "--log", default="ERROR",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR)"
    )

    args = parser.parse_args()

    level_name = args.log.upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    bands = list(map(int, args.bands.split(",")))

    gsm = AIR780EU(args.device_path, baudrate=115200)
    gsm.set_allowed_bands(bands)


if __name__ == "__main__":
    main()
