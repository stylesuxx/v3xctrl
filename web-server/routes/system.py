from flask_smorest import Blueprint
from flask import Response
from flask.views import MethodView
import socket
import subprocess
from typing import Tuple

from routes.response import success

blueprint = Blueprint('system', 'system', url_prefix='/system', description='System control endpoints')


@blueprint.route('/reboot')
class Reboot(MethodView):
    @blueprint.response(200, description="Force reboot the system")
    def post(self) -> Tuple[Response, int]:
        subprocess.run(["sudo", "reboot", "-f"])

        return success({"message": "Rebooting..."})


@blueprint.route('/shutdown')
class Shutdown(MethodView):
    @blueprint.response(200, description="Shutdown the system")
    def post(self) -> Tuple[Response, int]:
        subprocess.run(["sudo", "poweroff"])

        return success({"message": "Shutting down..."})


@blueprint.route('/dmesg')
class Dmesg(MethodView):
    @blueprint.response(200, description="Return output of dmesg")
    def get(self) -> Tuple[Response, int]:
        output = subprocess.check_output(
            ["dmesg"],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        return success({"log": output})


@blueprint.route("/info")
class Info(MethodView):
    @blueprint.response(200, description="Return system info including hostname and package versions")
    def get(self) -> Tuple[Response, int]:
        packages = [
            "v3xctrl",
            "v3xctrl-python",
        ]
        versions = {}

        for package in packages:
            try:
                result = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Version}", package],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                version = result.stdout.strip()
                versions[package] = version
            except subprocess.CalledProcessError:
                versions[package] = None

        return success({
            "hostname": socket.gethostname(),
            "packages": versions,
        })
