from flask_smorest import Blueprint
from flask import request
from flask.views import MethodView
import json
import subprocess
from typing import Tuple

from flask import Response

from routes.response import success, error

blueprint = Blueprint('camera', 'camera', url_prefix='/camera', description='Camera control endpoints')


@blueprint.route('/settings')
class CameraSettings(MethodView):
    @blueprint.response(200, description="Get current camera settings from the running pipeline")
    def get(self) -> Tuple[Response, int]:
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


@blueprint.route('/setting', methods=['POST'])
class CameraSetting(MethodView):
    @blueprint.response(200)
    def post(self) -> Tuple[Response, int]:
        """
        Set a camera setting via v3xctrl-video-control.

        Expected JSON payload:
        {
            "name": "brightness|contrast|saturation|sharpness|lens-position|analogue-gain|exposure-time",
            "value": <number>
        }
        """
        try:
            data = request.get_json()

            if not data:
                return error("No data provided", status=400)

            setting_name = data.get('name')
            value = data.get('value')

            if not setting_name or value is None:
                return error("Both 'name' and 'value' are required", status=400)

            output = subprocess.check_output(
                [
                    "v3xctrl-video-control",
                    "set",
                    "camera",
                    setting_name,
                    str(value)
                ],
                stderr=subprocess.STDOUT
            ).decode().strip()

            return success({
                "setting": setting_name,
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
