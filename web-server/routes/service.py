from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields
import subprocess
from typing import Dict, Any


class ServiceNameSchema(Schema):
    name = fields.Str(required=True)


blueprint = Blueprint('service', 'service', url_prefix='/service', description='Systemd service control')

SERVICES = [
    "v3xctrl-setup-env",
    "v3xctrl-config-server",
    "v3xctrl-wifi-mode",
    "v3xctrl-service-manager",
    "v3xctrl-video",
    "v3xctrl-control"
]


@blueprint.route('/')
class ListServices(MethodView):
    @blueprint.response(200, description="List all monitored systemd services with state info")
    def get(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"services": []}

        for service in SERVICES:
            try:
                output = subprocess.check_output(
                    ["systemctl", "show", service, "--property=Type,ActiveState,Result"],
                    stderr=subprocess.DEVNULL
                ).decode().strip()

                props = dict(line.split('=', 1) for line in output.splitlines())
                service_type = props.get("Type", "")
                active_state = props.get("ActiveState", "")
                result = props.get("Result", "")

            except subprocess.CalledProcessError:
                service_type = "unknown"
                active_state = "unknown"
                result = "error"

            data["services"].append({
                "name": service,
                "type": service_type,
                "state": active_state,
                "result": result
            })

        return data


@blueprint.route('/start')
class StartService(MethodView):
    @blueprint.arguments(ServiceNameSchema, location="json")
    @blueprint.response(200)
    def post(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = str(args['name'])
        subprocess.run(["sudo", "systemctl", "start", name])

        return {"message": f"Started service: {name}"}


@blueprint.route('/stop')
class StopService(MethodView):
    @blueprint.arguments(ServiceNameSchema, location="json")
    @blueprint.response(200)
    def post(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = str(args['name'])
        subprocess.run(["sudo", "systemctl", "stop", name])

        return {"message": f"Stopped service: {name}"}


@blueprint.route('/restart')
class RestartService(MethodView):
    @blueprint.arguments(ServiceNameSchema, location="json")
    @blueprint.response(200)
    def post(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = str(args['name'])
        subprocess.run(["sudo", "systemctl", "restart", name])

        return {"message": f"Restarted service: {name}"}


@blueprint.route('/log')
class LogService(MethodView):
    @blueprint.arguments(ServiceNameSchema, location="json")
    @blueprint.response(200)
    def post(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = str(args['name'])
        output = subprocess.check_output(
            ["journalctl", "-n", "50", "--no-page", "-u", name],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        return {"log": output}
