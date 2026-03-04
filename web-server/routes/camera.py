from flask_smorest import Blueprint
from flask import request
from flask.views import MethodView
import json
import subprocess

from flask import Response

from routes.response import success, error

blueprint = Blueprint('camera', 'camera', url_prefix='/camera', description='Camera control endpoints')


@blueprint.route('/settings')
class CameraSettings(MethodView):
    @blueprint.response(200, description="Get current camera settings from the running pipeline")
    def get(self) -> tuple[Response, int]:
        """
        Query live camera settings via v3xctrl-video-control.
        Requires the video pipeline to be running.
        """
        try:
            output = subprocess.check_output(
                ["v3xctrl-video-control", "list", "camera"],
                stderr=subprocess.STDOUT
            ).decode().strip()

            return success(json.loads(output))

        except subprocess.CalledProcessError as e:
            return error(
                "Failed to get camera settings",
                e.output.decode().strip() if e.output else "No output"
            )
        except Exception as e:
            return error("Unexpected error", str(e))


@blueprint.route('/settings/<name>')
class CameraSetting(MethodView):
    @blueprint.response(200, description="Get a single camera setting from the running pipeline")
    def get(self, name: str) -> tuple[Response, int]:
        try:
            output = subprocess.check_output(
                ["v3xctrl-video-control", "get", "camera", name],
                stderr=subprocess.STDOUT
            ).decode().strip()

            return success(json.loads(output))

        except subprocess.CalledProcessError as e:
            return error(
                f"Failed to get camera setting '{name}'",
                e.output.decode().strip() if e.output else "No output"
            )
        except Exception as e:
            return error("Unexpected error", str(e))

    @blueprint.response(200, description="Set a camera setting via v3xctrl-video-control")
    def put(self, name: str) -> tuple[Response, int]:
        try:
            data = request.get_json()

            if not data or 'value' not in data:
                return error("'value' is required", status=400)

            value = data['value']

            output = subprocess.check_output(
                ["v3xctrl-video-control", "set", "camera", name, str(value)],
                stderr=subprocess.STDOUT
            ).decode().strip()

            return success({
                "setting": name,
                "value": value,
                "output": output
            })

        except subprocess.CalledProcessError as e:
            return error(
                "Setting camera property failed",
                e.output.decode().strip() if e.output else "No output"
            )
        except Exception as e:
            return error("Unexpected error", str(e))
