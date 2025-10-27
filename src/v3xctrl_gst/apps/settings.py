import sys
import json

from v3xctrl_gst import ControlClient


def main() -> None:
    """Interactive CLI client."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Set property:    python control_client.py set <element> <property> <value> [socket_path]")
        print("  Get property:    python control_client.py get <element> <property> [socket_path]")
        print("  List properties: python control_client.py list <element> [socket_path]")
        print("  Stop pipeline:   python control_client.py stop [socket_path]")
        sys.exit(1)

    action = sys.argv[1]

    # Determine socket path (last arg if it starts with /)
    socket_path = '/tmp/v3xctrl.sock'
    if len(sys.argv) > 2 and sys.argv[-1].startswith('/'):
        socket_path = sys.argv[-1]
        sys.argv = sys.argv[:-1]  # Remove socket path from args

    client = ControlClient(socket_path)

    if action == 'set' and len(sys.argv) >= 5:
        element, prop, value = sys.argv[2], sys.argv[3], sys.argv[4]
        # Try to convert value to appropriate type
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass  # Keep as string
        response = client.set_property(element, prop, value)
        print(json.dumps(response, indent=2))

    elif action == 'get' and len(sys.argv) >= 4:
        element, prop = sys.argv[2], sys.argv[3]
        response = client.get_property(element, prop)
        print(json.dumps(response, indent=2))

    elif action == 'list' and len(sys.argv) >= 3:
        element = sys.argv[2]
        response = client.list_properties(element)
        print(json.dumps(response, indent=2))

    elif action == 'stop':
        response = client.stop_pipeline()
        print(json.dumps(response, indent=2))

    else:
        print("Invalid command")
        sys.exit(1)


if __name__ == '__main__':
    main()
