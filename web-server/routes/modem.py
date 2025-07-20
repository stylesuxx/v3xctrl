from flask import Blueprint, jsonify
import json
import subprocess

modem_blueprint = Blueprint('modem', __name__, url_prefix='/modem')


@modem_blueprint.route('/info', methods=['GET'])
def get_modem_info():
    output = subprocess.check_output(
        ["v3xctrl-modem-info"],
        stderr=subprocess.DEVNULL
    ).decode().strip()

    try:
        return jsonify(json.loads(output))
    except json.JSONDecodeError:
        return (jsonify({"error": "Invalid JSON output from modem info"}), 500)


@modem_blueprint.route('/reset', methods=['POST'])
def reset_modem():
    try:
        subprocess.check_output(
            ["v3xctrl-modem-reset"],
            stderr=subprocess.STDOUT
        ).decode().strip()

        return jsonify({})

    except subprocess.CalledProcessError as e:
        return jsonify({
            "error": "Modem reset failed",
            "details": e.output.decode().strip() if e.output else "No output"
        }), 500
