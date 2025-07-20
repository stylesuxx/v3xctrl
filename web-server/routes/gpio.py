from flask_smorest import Blueprint
from flask.views import MethodView
from marshmallow import Schema, fields as ma_fields
import subprocess

blueprint = Blueprint('gpio', 'gpio', url_prefix='/gpio', description='GPIO control endpoints')


class SetPwmSchema(Schema):
    gpio = ma_fields.Int(required=True, description="GPIO pin number")
    value = ma_fields.Int(required=True, description="PWM value")


@blueprint.route('/set-pwm')
class SetPwm(MethodView):
    @blueprint.arguments(SetPwmSchema, location="json")
    @blueprint.response(200, description="Set PWM value on a GPIO pin")
    def post(self, args):
        gpio = str(args['gpio'])
        value = str(args['value'])

        subprocess.run(["pigs", "s", gpio, value])

        return { "gpio": gpio, "value": value }
