import argparse
import json
import logging
from typing import Any

from atlib import AIR780EU

logger = logging.getLogger(__name__)


def query_field(description: str, func: Any) -> Any:
    try:
        return func()
    except Exception:
        logger.warning("Failed to query %s", description)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Query modem information.")
    parser.add_argument("device_path", help="Path to the modem (e.g. /dev/ttyACM0)")
    args = parser.parse_args()

    info: dict[str, Any] = {
        "version": None,
        "status": None,
        "allowedBands": [],
        "activeBand": None,
        "contexts": [],
        "addresses": [],
        "carrier": None,
    }

    gsm = AIR780EU(args.device_path, baudrate=115200)
    info["version"] = query_field("version", gsm.get_version)
    info["status"] = query_field("SIM status", gsm.get_sim_status)
    info["allowedBands"] = query_field("allowed bands", gsm.get_allowed_bands) or []
    info["activeBand"] = query_field("active band", gsm.get_active_band)
    info["contexts"] = [context._asdict() for context in (query_field("contexts", gsm.get_contexts) or [])]
    info["addresses"] = [address._asdict() for address in (query_field("addresses", gsm.get_addresses) or [])]
    info["carrier"] = query_field("carrier", gsm.get_current_operator)

    print(json.dumps(info))


if __name__ == "__main__":
    main()
