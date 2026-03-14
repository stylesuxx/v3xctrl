from flask_smorest import Blueprint
from flask import Response
from flask.views import MethodView
import json
import subprocess

from .response import success, error

blueprint = Blueprint('modem', 'modem', url_prefix='/modem', description='Modem control endpoints')


@blueprint.route('/')
class ModemInfo(MethodView):
    @blueprint.response(200)
    def get(self) -> tuple[Response, int]:
        try:
            output = subprocess.check_output(
                ["v3xctrl-modem-info"],
                stderr=subprocess.STDOUT
            ).decode().strip()

            return success(json.loads(output))
        except subprocess.CalledProcessError as e:
            return error(
                "Fetching modem info failed",
                e.output.decode().strip() if e.output else "No output"
            )


@blueprint.route('/reset')
class ModemReset(MethodView):
    @blueprint.response(200)
    def post(self) -> tuple[Response, int]:
        try:
            subprocess.check_output(
                ["v3xctrl-modem-reset"],
                stderr=subprocess.STDOUT
            ).decode().strip()

            return success()

        except subprocess.CalledProcessError as e:
            return error(
                "Modem reset failed",
                e.output.decode().strip() if e.output else "No output"
            )
