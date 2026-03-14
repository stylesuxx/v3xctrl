import subprocess

from flask import Response
from flask.views import MethodView
from flask_smorest import Blueprint

from .response import error, success

blueprint = Blueprint('service', 'service', url_prefix='/service', description='Systemd service control')

SERVICES = [
    "v3xctrl-setup-env",
    "v3xctrl-config-server",
    "v3xctrl-wifi-mode",
    "v3xctrl-service-manager",
    "v3xctrl-video",
    "v3xctrl-control",
    "v3xctrl-debug-log",
    "v3xctrl-reverse-shell",
]


@blueprint.route('/')
class ListServices(MethodView):
    @blueprint.response(200, description="List all monitored systemd services with state info")
    def get(self) -> tuple[Response, int]:
        services = []

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

            services.append({
                "name": service,
                "type": service_type,
                "state": active_state,
                "result": result
            })

        return success({"services": services})


@blueprint.route('/<name>')
class GetService(MethodView):
    @blueprint.response(200, description="Get status of a single systemd service")
    def get(self, name: str) -> tuple[Response, int]:
        try:
            output = subprocess.check_output(
                ["systemctl", "show", name, "--property=Type,ActiveState,Result"],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            props = dict(line.split('=', 1) for line in output.splitlines())
            return success({
                "name": name,
                "type": props.get("Type", ""),
                "state": props.get("ActiveState", ""),
                "result": props.get("Result", ""),
            })

        except subprocess.CalledProcessError:
            return success({
                "name": name,
                "type": "unknown",
                "state": "unknown",
                "result": "error",
            })


@blueprint.route('/<name>/start')
class StartService(MethodView):
    @blueprint.response(200)
    def post(self, name: str) -> tuple[Response, int]:
        try:
            subprocess.run(["sudo", "systemctl", "start", name],
                           check=True, capture_output=True, text=True)
            return success({"message": f"Started service: {name}"})
        except subprocess.CalledProcessError as e:
            return error(f"Failed to start service: {name}", e.stderr.strip())


@blueprint.route('/<name>/stop')
class StopService(MethodView):
    @blueprint.response(200)
    def post(self, name: str) -> tuple[Response, int]:
        try:
            subprocess.run(["sudo", "systemctl", "stop", name],
                           check=True, capture_output=True, text=True)
            return success({"message": f"Stopped service: {name}"})
        except subprocess.CalledProcessError as e:
            return error(f"Failed to stop service: {name}", e.stderr.strip())


@blueprint.route('/<name>/restart')
class RestartService(MethodView):
    @blueprint.response(200)
    def post(self, name: str) -> tuple[Response, int]:
        try:
            subprocess.run(["sudo", "systemctl", "restart", name],
                           check=True, capture_output=True, text=True)
            return success({"message": f"Restarted service: {name}"})
        except subprocess.CalledProcessError as e:
            return error(f"Failed to restart service: {name}", e.stderr.strip())


@blueprint.route('/<name>/log')
class ServiceLog(MethodView):
    @blueprint.response(200)
    def get(self, name: str) -> tuple[Response, int]:
        output = subprocess.check_output(
            ["journalctl", "-n", "50", "--no-page", "-u", name],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        return success({"log": output})
