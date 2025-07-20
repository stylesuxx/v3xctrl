from flask_smorest import Blueprint
from flask.views import MethodView
from flask import request, current_app
import subprocess
import json

blueprint = Blueprint('config', 'config', url_prefix='/config', description='Configuration management')


@blueprint.route('/save')
class SaveConfig(MethodView):
    @blueprint.response(200, description="Save configuration and regenerate environment file")
    def post(self):
        data = request.json

        with open(current_app.config['CONFIG_PATH'], 'w') as f:
            json.dump(data, f, indent=4)

        subprocess.run(["sudo", "/usr/bin/v3xctrl-write-env"])

        return {"message": "Saved!"}
