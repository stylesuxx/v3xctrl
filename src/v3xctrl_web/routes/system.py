import socket
import subprocess
from pathlib import Path

from flask import Response, send_file
from flask.views import MethodView
from flask_smorest import Blueprint

from .response import error, success

blueprint = Blueprint("system", "system", url_prefix="/system", description="System control endpoints")


@blueprint.route("/reboot")
class Reboot(MethodView):
    @blueprint.response(200, description="Force reboot the system")
    def post(self) -> tuple[Response, int]:
        subprocess.run(["sudo", "reboot", "-f"])

        return success({"message": "Rebooting..."})


@blueprint.route("/shutdown")
class Shutdown(MethodView):
    @blueprint.response(200, description="Shutdown the system")
    def post(self) -> tuple[Response, int]:
        subprocess.run(["sudo", "poweroff"])

        return success({"message": "Shutting down..."})


@blueprint.route("/dmesg")
class Dmesg(MethodView):
    @blueprint.response(200, description="Return output of dmesg")
    def get(self) -> tuple[Response, int]:
        output = subprocess.check_output(["dmesg"], stderr=subprocess.DEVNULL).decode().strip()

        return success({"log": output})


@blueprint.route("/info")
class Info(MethodView):
    @blueprint.response(200, description="Return system info including hostname and package versions")
    def get(self) -> tuple[Response, int]:
        packages = [
            "v3xctrl",
            "v3xctrl-python",
        ]
        versions = {}

        for package in packages:
            try:
                result = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Version}", package],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                version = result.stdout.strip()
                versions[package] = version
            except subprocess.CalledProcessError:
                versions[package] = None

        return success(
            {
                "hostname": socket.gethostname(),
                "packages": versions,
            }
        )


JOURNAL_DIR = Path("/data/journal")


@blueprint.route("/logs")
class LogArchives(MethodView):
    @blueprint.response(200, description="List available log archives")
    def get(self) -> tuple[Response, int]:
        archives = []
        if JOURNAL_DIR.exists():
            for filepath in sorted(JOURNAL_DIR.glob("archive_*.tar.gz"), reverse=True):
                archives.append(
                    {
                        "name": filepath.name,
                        "size": filepath.stat().st_size,
                    }
                )
        return success({"archives": archives})


@blueprint.route("/logs/<filename>")
class LogArchiveDownload(MethodView):
    @blueprint.response(200, description="Download a log archive")
    def get(self, filename: str) -> Response:
        filepath = JOURNAL_DIR / filename
        if not filepath.name.startswith("archive_") or not filepath.name.endswith(".tar.gz"):
            return error("Invalid filename", status=400)
        if not filepath.exists():
            return error("Archive not found", status=404)
        return send_file(filepath, as_attachment=True)
