from flask_smorest import Blueprint
from flask import jsonify, Response, request
from flask.views import MethodView
import subprocess
from typing import Tuple

blueprint = Blueprint('camera', 'camera', url_prefix='/camera', description='Camera control endpoints')


@blueprint.route('/setting', methods=['POST'])
class CameraSetting(MethodView):
    @blueprint.response(200)
    def post(self) -> Response | Tuple[Response, int]:
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
                return (jsonify({
                    "error": "No data provided"
                }), 400)

            setting_name = data.get('name')
            value = data.get('value')

            if not setting_name or value is None:
                return (jsonify({
                    "error": "Both 'name' and 'value' are required"
                }), 400)

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

            return jsonify({
                "success": True,
                "setting": setting_name,
                "value": value,
                "output": output
            })

        except subprocess.CalledProcessError as e:
            return (jsonify({
                "error": "Setting camera property failed",
                "details": e.output.decode().strip() if e.output else "No output"
            }), 500)
        except Exception as e:
            return (jsonify({
                "error": "Unexpected error",
                "details": str(e)
            }), 500)
