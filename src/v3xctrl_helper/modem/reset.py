import argparse
import logging
from atlib import AIR780EU
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset modem to auto connect and a single empty IPv4 APN")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
    parser.add_argument(
        "--bands",
        help="Comma-separated list of LTE band integers (e.g. 1,3,7,20)",
        type=lambda s: [int(x) for x in s.split(',')] if s else [],
        default=[]
    )
    args = parser.parse_args()

    # Connect to modem, turn radio off, set operator to auto connect
    gsm = AIR780EU(args.device_path, baudrate=115200)
    gsm.off()
    gsm.set_operator_auto()

    # Delete all available contexts
    contexts = gsm.get_contexts()
    for context in contexts:
        id = context.id
        gsm.delete_context(id)

    if len(args.bands) > 0:
        gsm.set_allowed_bands(args.bands)

    # Reboots the modem, serial connection will be lost, radio will be powered
    # back on during a reboot cycle.
    try:
        gsm.reboot()
    except OSError:
        logging.warning("Lost connection during reboot...")

    # Give the modem some time to reboot
    time.sleep(5)


if __name__ == "__main__":
    main()
