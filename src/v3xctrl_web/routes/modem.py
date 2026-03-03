import json
import subprocess

from flask import Response, current_app
from flask.views import MethodView
from flask_smorest import Blueprint

from .response import error, success

blueprint = Blueprint("modem", "modem", url_prefix="/modem", description="Modem control endpoints")


SUBPROCESS_TIMEOUT = 90


@blueprint.route("/")
class ModemInfo(MethodView):
    @blueprint.response(200)
    def get(self) -> tuple[Response, int]:
        try:
            output = (
                subprocess.check_output(["v3xctrl-modem-info"], stderr=subprocess.STDOUT, timeout=SUBPROCESS_TIMEOUT)
                .decode()
                .strip()
            )

            return success(json.loads(output))
        except subprocess.TimeoutExpired:
            return error("Modem info request timed out", "The modem did not respond in time")
        except subprocess.CalledProcessError as exception:
            return error(
                "Fetching modem info failed",
                exception.output.decode().strip() if exception.output else "No output",
            )
        except Exception as exception:
            return error("Fetching modem info failed", str(exception))


@blueprint.route("/models")
class ModemModels(MethodView):
    @blueprint.response(200, description="Return supported modem models with their valid bands")
    def get(self) -> tuple[Response, int]:
        modems_path: str = str(current_app.config["MODEMS_PATH"])
        with open(modems_path) as f:
            return success(json.load(f))


@blueprint.route("/reset")
class ModemReset(MethodView):
    @blueprint.response(200)
    def post(self) -> tuple[Response, int]:
        try:
            subprocess.check_output(
                ["v3xctrl-modem-reset"], stderr=subprocess.STDOUT, timeout=SUBPROCESS_TIMEOUT
            ).decode().strip()

            return success()
        except subprocess.TimeoutExpired:
            return error("Modem reset timed out", "The modem did not respond in time")
        except subprocess.CalledProcessError as exception:
            return error(
                "Modem reset failed",
                exception.output.decode().strip() if exception.output else "No output",
            )
        except Exception as exception:
            return error("Modem reset failed", str(exception))
