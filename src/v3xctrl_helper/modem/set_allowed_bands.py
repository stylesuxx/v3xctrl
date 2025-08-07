import argparse
from atlib import AIR780EU


def main() -> None:
    parser = argparse.ArgumentParser(description="Set allowed LTE bands on AIR780EU modem.")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
    parser.add_argument("bands", help="Comma-separated list of LTE band integers (e.g. 1,3,7,20)")
    args = parser.parse_args()

    bands = list(map(int, args.bands.split(",")))

    gsm = AIR780EU(args.device_path, baudrate=115200)
    gsm.set_allowed_bands(bands)


if __name__ == "__main__":
    main()
