import json
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Mock rpi_servo_pwm before any app imports (gpio.py imports it at module level)
_mock_rpi_servo_pwm = ModuleType("rpi_servo_pwm")
_mock_rpi_servo_pwm.HardwarePWM = MagicMock()  # type: ignore[attr-defined]
sys.modules["rpi_servo_pwm"] = _mock_rpi_servo_pwm

from v3xctrl_web.__main__ import create_app  # noqa: E402


@pytest.fixture()
def sample_schema():
    return {
        "type": "object",
        "properties": {
            "hostname": {"type": "string"},
        },
    }


@pytest.fixture()
def sample_config():
    return {"hostname": "v3xctrl", "wifi_mode": "ap"}


@pytest.fixture()
def sample_modems():
    return [{"name": "quectel", "path": "/dev/ttyUSB2"}]


@pytest.fixture()
def app(tmp_path, sample_schema, sample_config, sample_modems):
    schema_path = tmp_path / "schema.json"
    config_path = tmp_path / "config.json"
    modems_path = tmp_path / "modems.json"

    schema_path.write_text(json.dumps(sample_schema))
    config_path.write_text(json.dumps(sample_config))
    modems_path.write_text(json.dumps(sample_modems))

    app = create_app(
        schema_path=str(schema_path),
        config_path=str(config_path),
        modems_path=str(modems_path),
    )
    app.config["TESTING"] = True

    return app


@pytest.fixture()
def client(app):
    return app.test_client()
