import argparse
import subprocess
from flask import Flask, render_template, request, jsonify
import json

app = Flask(__name__, template_folder='templates', static_folder='static')

schema_path = None
config_path = None


@app.route('/')
def index():
    with open(schema_path) as f:
        schema = json.load(f)
    with open(config_path) as f:
        config = json.load(f)

    return render_template('index.html', schema=schema, config=config)


@app.route('/save', methods=['POST'])
def save_config():
    data = request.json
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)

    return jsonify({"message": "Saved!"})


@app.route('/services', methods=['GET'])
def get_services():
    services = [
        "rc-transmit-camera",
        "rc-config-server",
        "rc-wifi-mode",
        "rc-control",
        "rc-service-manager"
    ]

    data = {"services": []}

    for service in services:
        try:
            output = subprocess.check_output(
                ["systemctl", "show", service, "--property=Type,ActiveState,Result"],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            props = dict(line.split('=', 1) for line in output.splitlines())
            service_type = props.get("Type", "")
            active_state = props.get("ActiveState", "")
            result = props.get("Result", "")

            if service_type == "oneshot":
                # oneshot services should finish and result=success
                is_success = (active_state == "inactive" and result == "success")
            else:
                # all other services should be actively running
                is_success = (active_state == "active")

        except subprocess.CalledProcessError:
            is_success = False
            service_type = "unknown"
            result = "error"

        data["services"].append({
            "name": service,
            "type": service_type,
            "active": is_success,
            "result": result
        })

    return jsonify(data)


def main():
    global schema_path, config_path

    parser = argparse.ArgumentParser(description="Run the Form Editor server.")
    parser.add_argument('--schema', required=True, help='Path to schema.json')
    parser.add_argument('--config', required=True, help='Path to config.json')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', default=5000, type=int, help='Port to run the server on')
    args = parser.parse_args()

    schema_path = args.schema
    config_path = args.config

    app.run(debug=True, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
