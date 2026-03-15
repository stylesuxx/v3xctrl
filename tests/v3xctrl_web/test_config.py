import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetConfig:
    def test_success(self, client, sample_config):
        response = client.get("/config/")

        assert response.status_code == 200
        assert response.get_json()["data"] == sample_config

    def test_file_not_found(self, client, app):
        app.config["CONFIG_PATH"] = "/nonexistent/config.json"

        with pytest.raises(FileNotFoundError):
            client.get("/config/")


class TestPutConfig:
    def test_save_success(self, client, app):
        with patch("v3xctrl_web.routes.config.subprocess.run") as mock_run:
            mock_run.return_value = type("Result", (), {"returncode": 0, "stderr": ""})()

            new_config = {"hostname": "updated", "wifi_mode": "client"}
            response = client.put("/config/", json=new_config)

            assert response.status_code == 200
            assert response.get_json()["data"]["message"] == "Saved!"

            # Verify the config was actually written
            config_path = Path(app.config["CONFIG_PATH"])
            saved = json.loads(config_path.read_text())
            assert saved == new_config

    def test_no_json_data(self, client):
        response = client.put("/config/", content_type="application/json", data="null")

        error = response.get_json()["error"]
        assert "No JSON data provided" in error["message"]

    def test_backup_created(self, client, app):
        with patch("v3xctrl_web.routes.config.subprocess.run") as mock_run:
            mock_run.return_value = type("Result", (), {"returncode": 0, "stderr": ""})()

            config_path = Path(app.config["CONFIG_PATH"])
            original_content = config_path.read_text()

            client.put("/config/", json={"hostname": "new"})

            backup_path = config_path.with_suffix(config_path.suffix + ".old")
            assert backup_path.exists()
            assert json.loads(backup_path.read_text()) == json.loads(original_content)

    def test_env_regeneration_failure(self, client, app):
        with patch("v3xctrl_web.routes.config.subprocess.run") as mock_run:
            mock_run.return_value = type("Result", (), {"returncode": 1, "stderr": "write-env failed"})()

            response = client.put("/config/", json={"hostname": "new"})

            error = response.get_json()["error"]
            assert "Environment regeneration failed" in error["message"]
            assert error["details"] == "write-env failed"

    def test_subprocess_timeout(self, client, app):
        with patch("v3xctrl_web.routes.config.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("v3xctrl-write-env", 10)

            response = client.put("/config/", json={"hostname": "new"})

            error = response.get_json()["error"]
            assert "timed out" in error["message"]

    def test_restore_backup_on_failure(self, client, app):
        config_path = Path(app.config["CONFIG_PATH"])
        original_config = json.loads(config_path.read_text())

        with patch("v3xctrl_web.routes.config.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("disk full")

            response = client.put("/config/", json={"hostname": "new"})

            assert response.get_json()["error"] is not None
            # Original config should be restored from backup
            restored = json.loads(config_path.read_text())
            assert restored == original_config

    def test_temp_file_cleaned_up(self, client, app):
        with patch("v3xctrl_web.routes.config.subprocess.run") as mock_run:
            mock_run.return_value = type("Result", (), {"returncode": 0, "stderr": ""})()

            client.put("/config/", json={"hostname": "new"})

            config_path = Path(app.config["CONFIG_PATH"])
            temp_path = config_path.with_suffix(config_path.suffix + ".tmp")
            assert not temp_path.exists()


class TestGetSchema:
    def test_success(self, client, sample_schema):
        response = client.get("/config/schema")

        assert response.status_code == 200
        assert response.get_json()["data"] == sample_schema
