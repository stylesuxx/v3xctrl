from flask_smorest import Blueprint
from flask.views import MethodView
from marshmallow import Schema, fields
from rpi_servo_pwm import HardwarePWM

blueprint = Blueprint('gpio', 'gpio', url_prefix='/gpio', description='GPIO control endpoints')


class SetPwmSchema(Schema):
    channel = fields.Int(required=True)
    value = fields.Int(required=True)


@blueprint.route('/set-pwm')
class SetPwm(MethodView):
    @blueprint.arguments(SetPwmSchema, location="json")
    @blueprint.response(200, description="Set PWM value on a GPIO pin")
    def post(self, args):
        channel = int(args['channel'])
        value = int(args['value'])

        # Enable hardware PWM and set the value, do not close since we might be
        # in process of calibration and need to keep sending continous signal.
        pwm = HardwarePWM(channel)
        pwm.setup(value)

        return {"gpio": channel, "value": value}
