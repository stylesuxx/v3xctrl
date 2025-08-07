import argparse
from atlib import AIR780EU
import json
from typing import Dict, Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Query modem information.")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
    args = parser.parse_args()

    info: Dict[str, Any] = {
        "version": None,
        "status": None,
        "allowedBands": [],
        "activeBand": None,
        "contexts": [],
        "carrier": None,
    }

    gsm = AIR780EU(args.device_path, baudrate=115200)
    info["version"] = gsm.get_version()
    info["status"] = gsm.get_sim_status()
    info["allowedBands"] = gsm.get_allowed_bands()
    info["activeBand"] = gsm.get_active_band()
    info["contexts"] = [contexts._asdict() for contexts in gsm.get_contexts()]
    info["addresses"] = [addresses._asdict() for addresses in gsm.get_addresses()]
    info["carrier"] = gsm.get_current_operator()

    print(json.dumps(info))


if __name__ == "__main__":
    main()
