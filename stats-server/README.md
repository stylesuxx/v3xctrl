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

### CLI Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--relay-port` | Yes | - | Relay server port (repeatable for multiple relays) |
| `--users-file` | Yes | - | Path to users.json |
| `--secret-key` | No | Random | Secret key for session signing |
| `--host` | No | 0.0.0.0 | Host to bind to |
| `--port` | No | 8080 | Port to listen on |
