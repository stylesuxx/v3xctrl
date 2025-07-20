from flask_smorest import Blueprint
from flask.views import MethodView
import subprocess

blueprint = Blueprint('streamer', 'streamer', url_prefix='/streamer', description='System control endpoints')


@blueprint.route('/reboot')
class Reboot(MethodView):
    @blueprint.response(200, description="Force reboot the system")
    def post(self):
        subprocess.run(["sudo", "reboot", "-f"])

        return {"message": "Rebooting..."}


@blueprint.route('/shutdown')
class Shutdown(MethodView):
    @blueprint.response(200, description="Shutdown the system")
    def post(self):
        subprocess.run(["sudo", "shutdown", "now"])

        return {"message": "Shutting down..."}


@blueprint.route('/dmesg')
class Dmesg(MethodView):
    @blueprint.response(200, description="Return output of dmesg")
    def get(self):
        output = subprocess.check_output(
            ["dmesg"],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        return {"log": output}
