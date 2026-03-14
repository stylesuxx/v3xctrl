import contextlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import Response, current_app, request
from flask.views import MethodView
from flask_smorest import Blueprint

from .response import error, success

blueprint = Blueprint('config', 'config', url_prefix='/config', description='Configuration management')


@blueprint.route('/')
class Config(MethodView):
    @blueprint.response(200, description="Return current configuration")
    def get(self) -> tuple[Response, int]:
        config_path: str = str(current_app.config['CONFIG_PATH'])
        with open(config_path) as f:
            return success(json.load(f))

    @blueprint.response(200, description="Save configuration and regenerate environment file")
    def put(self) -> tuple[Response, int]:
        data = request.json

        if data is None:
            return error("No JSON data provided", status=400)

        config_path: str = str(current_app.config['CONFIG_PATH'])
        config_path_obj = Path(config_path)
        backup_path = config_path_obj.with_suffix(config_path_obj.suffix + '.old')
        temp_path = config_path_obj.with_suffix(config_path_obj.suffix + '.tmp')

        try:
            # Backup existing config if it exists
            if config_path_obj.exists():
                shutil.copy2(config_path, backup_path)

            # Write to temporary file with fsync
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            temp_path.rename(config_path)

            result = subprocess.run(
                ["sudo", "/usr/bin/v3xctrl-write-env"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return error("Environment regeneration failed", result.stderr)

            return success({"message": "Saved!"})

        except subprocess.TimeoutExpired:
            return error("Environment regeneration timed out")

        except Exception as e:
            # If something went wrong, try to restore from backup
            if backup_path.exists():
                with contextlib.suppress(Exception):
                    shutil.copy2(backup_path, config_path)

            return error(f"Failed to save configuration: {e!s}")

        finally:
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()


@blueprint.route('/schema')
class ConfigSchema(MethodView):
    @blueprint.response(200, description="Return configuration JSON schema")
    def get(self) -> tuple[Response, int]:
        schema_path: str = str(current_app.config['SCHEMA_PATH'])
        with open(schema_path) as f:
            return success(json.load(f))
