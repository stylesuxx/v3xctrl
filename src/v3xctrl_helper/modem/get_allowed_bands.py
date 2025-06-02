import argparse
from atlib import AIR780EU
import json


def main():
    parser = argparse.ArgumentParser(description="Query allowed LTE bands from AIR780EU modem.")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
    args = parser.parse_args()

    gsm = AIR780EU(args.device_path, baudrate=115200)
    allowed_bands = gsm.get_allowed_bands()
    print(json.dumps(allowed_bands))


if __name__ == "__main__":
    main()
