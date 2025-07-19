from flask import Blueprint, jsonify
import json
import subprocess

modem_blueprint = Blueprint('modem', __name__, url_prefix='/modem')


@modem_blueprint.route('/info', methods=['GET'])
def info():
    try:
        output = subprocess.check_output(
            ["v3xctrl-modem-info"],
            stderr=subprocess.STDOUT
        ).decode().strip()

        return jsonify(json.loads(output))
    except subprocess.CalledProcessError as e:
        return (jsonify({
            "error": "Fetching modem info failed",
            "details": e.output.decode().strip() if e.output else "No output"
        }), 500)


@modem_blueprint.route('/reset', methods=['POST'])
def reset():
    try:
        subprocess.check_output(
            ["v3xctrl-modem-reset"],
            stderr=subprocess.STDOUT
        ).decode().strip()

        return jsonify({})

    except subprocess.CalledProcessError as e:
        return (jsonify({
            "error": "Modem reset failed",
            "details": e.output.decode().strip() if e.output else "No output"
        }), 500)
