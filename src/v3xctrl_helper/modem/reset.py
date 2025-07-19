import argparse
from atlib import AIR780EU


def main():
    parser = argparse.ArgumentParser(description="Reset modem to auto connect and a single empty IPv4 APN")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
    args = parser.parse_args()

    gsm = AIR780EU(args.device_path, baudrate=115200)
    gsm.set_operator_auto()

    # Delete all available contexts
    contexts = gsm.get_contexts()
    for context in contexts:
        id = context.id
        gsm.delete_context(id)

    # Set empty IPv4 context
    gsm.set_context(1, "IP")
    gsm.reboot()


if __name__ == "__main__":
    main()
