# Stats Server

Web dashboard for monitoring UDP relay sessions.

## Setup

```bash
pip install -r requirements.txt
```

## User Management

Users are stored in a JSON file with werkzeug-hashed passwords. Use `manage_users.py` to manage them:

```bash
# Add a new user (prompts for password)
python manage_users.py /path/to/users.json add admin

# Update an existing user's password
python manage_users.py /path/to/users.json add admin

# Remove a user
python manage_users.py /path/to/users.json remove admin

# List all users
python manage_users.py /path/to/users.json list
```

## Running

```bash
python main.py \
  --relay-port 8888 \
  --relay-port 9999 \
  --users-file /path/to/users.json \
  --port 8080
```

On a relay host installed from `build/packages/relay/`, the settings come from
`/etc/v3xctrl/relay.toml` instead:

```bash
python main.py
```

```toml
[paths]
users_file = "/var/lib/v3xctrl/users.json"

[stats]
relay_ports = [8888, 9999]
port = 8080
secret_key = "..."
```

A command line argument always wins over the configuration file, and the file
may be absent, in which case `--relay-port` and `--users-file` have to be given.

### CLI Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--relay-port` | Yes, unless `stats.relay_ports` is set | - | Relay server port (repeatable for multiple relays) |
| `--users-file` | Yes, unless `paths.users_file` is set | - | Path to users.json |
| `--secret-key` | No | `stats.secret_key`, else random per restart | Secret key for session signing |
| `--host` | No | 0.0.0.0 | Host to bind to |
| `--port` | No | `stats.port`, else 8080 | Port to listen on |
| `--runtime-dir` | No | `paths.runtime_directory`, else /run/v3xctrl | Directory holding the relay command sockets |
| `--config` | No | /etc/v3xctrl/relay.toml | Path to the configuration file |

A random secret key per restart invalidates every login session, so pin
`stats.secret_key` on a host where the service restarts automatically.
