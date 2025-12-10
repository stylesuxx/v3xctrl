import json
import argparse
from typing import Any

from v3xctrl_gst import ControlClient


actions = [
    'set',
    'get',
    'list',
    'stop',
    'record',
    'stats',
]


def main() -> None:
    parser = argparse.ArgumentParser(description='GStreamer pipeline control client')
    parser.add_argument('action', choices=actions, help='Action to perform')
    parser.add_argument('element', nargs='?', help='Element name')
    parser.add_argument('property', nargs='?', help='Property name')
    parser.add_argument('value', nargs='?', help='Property value')
    parser.add_argument('socket_path', nargs='?', default='/tmp/v3xctrl.sock',
                        help='Path to Unix socket (default: /tmp/v3xctrl.sock)')
    args = parser.parse_args()

    # Validate arguments based on action
    if args.action == 'set':
        if not args.element or not args.property or not args.value:
            parser.error("set requires: element property value")

    elif args.action == 'get':
        if not args.element or not args.property:
            parser.error("get requires: element property")

    elif args.action == 'list':
        if not args.element:
            parser.error("list requires: element")

    elif args.action == 'record':
        if not args.element:
            parser.error("record requires: element")

    client = ControlClient(args.socket_path)

    response = None
    if args.action == 'set':
        # Try to convert value to appropriate type
        value: Any = args.value
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass  # Keep as string
        response = client.set_property(args.element, args.property, value)

    elif args.action == 'get':
        response = client.get_property(args.element, args.property)

    elif args.action == 'list':
        response = client.list_properties(args.element)

    elif args.action == 'stop':
        response = client.stop()

    elif args.action == 'record':
        response = client.record(args.element)

    elif args.action == 'stats':
        response = client.stats()

    print(json.dumps(response, indent=2))


if __name__ == '__main__':
    main()
