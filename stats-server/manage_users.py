#!/usr/bin/env python3
"""CLI tool to manage users for the stats web interface."""

import argparse
import json
import sys


def load_users(path: str) -> dict[str, str | None]:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_users(path: str, users: dict[str, str | None]) -> None:
    with open(path, 'w') as f:
        json.dump(users, f, indent=2)
        f.write('\n')


def cmd_add(args: argparse.Namespace) -> None:
    users = load_users(args.file)
    action = "Reset" if args.username in users else "Added"
    users[args.username] = None
    save_users(args.file, users)
    print(f"{action} user '{args.username}' (password will be set on first login)")


def cmd_remove(args: argparse.Namespace) -> None:
    users = load_users(args.file)
    if args.username not in users:
        print(f"Error: user '{args.username}' not found", file=sys.stderr)
        sys.exit(1)

    del users[args.username]
    save_users(args.file, users)
    print(f"Removed user '{args.username}'")


def cmd_list(args: argparse.Namespace) -> None:
    users = load_users(args.file)
    if not users:
        print("No users configured")
        return

    for username in sorted(users):
        print(f"  {username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage stats interface users")
    parser.add_argument('file', help='Path to users.json')

    subparsers = parser.add_subparsers(dest='command', required=True)

    add_parser = subparsers.add_parser('add', help='Add a user or reset their password')
    add_parser.add_argument('username', help='Username to add')
    add_parser.set_defaults(func=cmd_add)

    remove_parser = subparsers.add_parser('remove', help='Remove a user')
    remove_parser.add_argument('username', help='Username to remove')
    remove_parser.set_defaults(func=cmd_remove)

    list_parser = subparsers.add_parser('list', help='List all users')
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
