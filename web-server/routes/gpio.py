from flask_smorest import Blueprint
from flask import Response, request
from flask.views import MethodView
from rpi_servo_pwm import HardwarePWM
from typing import Tuple

from routes.response import success, error

blueprint = Blueprint('gpio', 'gpio', url_prefix='/gpio', description='GPIO control endpoints')


@blueprint.route('/<int:channel>/pwm')
class Pwm(MethodView):
    @blueprint.response(200, description="Set PWM value on a GPIO pin")
    def put(self, channel: int) -> Tuple[Response, int]:
        data = request.get_json()

        if not data or 'value' not in data:
            return error("'value' is required", status=400)

        value = int(data['value'])

        # Enable hardware PWM and set the value, do not close since we might be
        # in process of calibration and need to keep sending continous signal.
        pwm = HardwarePWM(channel)
        pwm.setup(value)

        return success({"gpio": channel, "value": value})
