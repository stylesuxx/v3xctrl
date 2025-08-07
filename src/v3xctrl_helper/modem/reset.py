import argparse
from atlib import AIR780EU


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset modem to auto connect and a single empty IPv4 APN")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
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

    # Reboots the modem, serial connection will be lost, radio will be powered
    # back on during a reboot cycle.
    gsm.reboot()


if __name__ == "__main__":
    main()
