from flask_smorest import Blueprint
from flask.views import MethodView
import subprocess
from typing import Dict, Any

blueprint = Blueprint('streamer', 'streamer', url_prefix='/streamer', description='System control endpoints')


@blueprint.route('/reboot')
class Reboot(MethodView):
    @blueprint.response(200, description="Force reboot the system")
    def post(self) -> Dict[str, Any]:
        subprocess.run(["sudo", "reboot", "-f"])

        return {"message": "Rebooting..."}


@blueprint.route('/shutdown')
class Shutdown(MethodView):
    @blueprint.response(200, description="Shutdown the system")
    def post(self) -> Dict[str, Any]:
        subprocess.run(["sudo", "poweroff"])

        return {"message": "Shutting down..."}


@blueprint.route('/dmesg')
class Dmesg(MethodView):
    @blueprint.response(200, description="Return output of dmesg")
    def get(self) -> Dict[str, Any]:
        output = subprocess.check_output(
            ["dmesg"],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        return {"log": output}


@blueprint.route("/version")
class Version(MethodView):
    @blueprint.response(200, description="Return package versions")
    def get(self) -> Dict[str, Any]:
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

        return versions
