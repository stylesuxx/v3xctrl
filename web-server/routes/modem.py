from flask_smorest import Blueprint
from flask import jsonify, Response
from flask.views import MethodView
import json
import subprocess
from typing import Tuple

blueprint = Blueprint('modem', 'modem', url_prefix='/modem', description='Modem control endpoints')


@blueprint.route('/info')
class ModemInfo(MethodView):
    @blueprint.response(200)
    def get(self) -> Response | Tuple[Response, int]:
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


@blueprint.route('/reset')
class ModemReset(MethodView):
    @blueprint.response(200)
    def post(self) -> Response | Tuple[Response, int]:
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
