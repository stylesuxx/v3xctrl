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

    # Write env file
    subprocess.run(["sudo", "/usr/bin/v3xctrl-write-env"])

    return jsonify({"message": "Saved!"})


@app.route('/reboot', methods=['POST'])
def reboot():
    subprocess.run(["sudo", "reboot", "-f"])
    return jsonify({"message": "Rebooting..."})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    subprocess.run(["sudo", "shutdown", "now"])
    return jsonify({"message": "Shutting down..."})

@app.route('/set-pwm', methods=['POST'])
def set_pwm():
    data = request.json

    gpio = str(data['gpio'])
    value = str(data['value'])

    subprocess.run(["pigs", "s", gpio, value])
    return jsonify({gpio: gpio, value: value})


@app.route('/service/start', methods=['POST'])
def start_service():
    data = request.json
    name = str(data['name'])

    subprocess.run(["sudo", "systemctl", "start", name])
    return jsonify({"message": f"Started service: {name}"})


@app.route('/service/stop', methods=['POST'])
def stop_service():
    data = request.json
    name = str(data['name'])

    subprocess.run(["sudo", "systemctl", "stop", name])
    return jsonify({"message": f"Stopped service: {name}"})


@app.route('/service/restart', methods=['POST'])
def restart_service():
    data = request.json
    name = str(data['name'])

    subprocess.run(["sudo", "systemctl", "restart", name])
    return jsonify({"message": f"Restarted service: {name}"})


@app.route('/service/log', methods=['POST'])
def get_log():
    data = request.json
    name = str(data['name'])

    output = subprocess.check_output(
        ["journalctl", "-n", "50", "--no-page", "-u", name],
        stderr=subprocess.DEVNULL
    ).decode().strip()

    return jsonify({
      "log": output
    })


@app.route('/dmesg', methods=['GET'])
def get_dmesg():
    output = subprocess.check_output(
        ["dmesg"],
        stderr=subprocess.DEVNULL
    ).decode().strip()

    return jsonify({
      "log": output
    })


@app.route('/modem/bands', methods=['GET'])
def get_modem_bands():
    output = subprocess.check_output(
        ["v3xctrl-get-bands"],
        stderr=subprocess.DEVNULL
    ).decode().strip()

    return output


@app.route('/services', methods=['GET'])
def get_services():
    services = [
        "v3xctrl-setup-env",
        "v3xctrl-config-server",
        "v3xctrl-wifi-mode",
        "v3xctrl-service-manager",
        "v3xctrl-video",
        "v3xctrl-control"
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

        except subprocess.CalledProcessError:
            service_type = "unknown"
            active_state = "unknown"
            result = "error"

        data["services"].append({
            "name": service,
            "type": service_type,
            "state": active_state,
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
