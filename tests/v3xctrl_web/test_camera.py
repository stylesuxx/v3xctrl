import subprocess
from unittest.mock import patch


class TestCameraSettings:
    def test_list_settings(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.return_value = b'{"brightness": 50, "contrast": 32}'

            response = client.get("/camera/settings")

            assert response.status_code == 200
            data = response.get_json()["data"]
            assert data["brightness"] == 50
            assert data["contrast"] == 32

    def test_list_settings_subprocess_failure(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(
                1, "v3xctrl-video-control", output=b"pipeline not running"
            )

            response = client.get("/camera/settings")

            error = response.get_json()["error"]
            assert error["message"] == "Failed to get camera settings"
            assert error["details"] == "pipeline not running"

    def test_list_settings_unexpected_error(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.side_effect = RuntimeError("unexpected")

            response = client.get("/camera/settings")

            error = response.get_json()["error"]
            assert error["message"] == "Unexpected error"
            assert error["details"] == "unexpected"


class TestCameraSetting:
    def test_get_setting(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.return_value = b'{"brightness": 50}'

            response = client.get("/camera/settings/brightness")

            assert response.status_code == 200
            assert response.get_json()["data"]["brightness"] == 50

    def test_get_setting_subprocess_failure(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "v3xctrl-video-control", output=b"not found")

            response = client.get("/camera/settings/nonexistent")

            error = response.get_json()["error"]
            assert "nonexistent" in error["message"]

    def test_get_setting_unexpected_error(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.side_effect = ValueError("bad value")

            response = client.get("/camera/settings/brightness")

            assert response.get_json()["error"]["message"] == "Unexpected error"

    def test_put_setting(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.return_value = b"OK"

            response = client.put("/camera/settings/brightness", json={"value": 75})

            assert response.status_code == 200
            data = response.get_json()["data"]
            assert data["setting"] == "brightness"
            assert data["value"] == 75
            assert data["output"] == "OK"

    def test_put_setting_missing_value(self, client):
        response = client.put("/camera/settings/brightness", json={})

        error = response.get_json()["error"]
        assert "'value' is required" in error["message"]

    def test_put_setting_no_content_type(self, client):
        response = client.put("/camera/settings/brightness")

        assert response.status_code == 500
        assert response.get_json()["error"]["message"] == "Unexpected error"

    def test_put_setting_subprocess_failure(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "v3xctrl-video-control", output=b"invalid value")

            response = client.put("/camera/settings/brightness", json={"value": -1})

            error = response.get_json()["error"]
            assert error["message"] == "Setting camera property failed"
            assert error["details"] == "invalid value"

    def test_put_setting_unexpected_error(self, client):
        with patch("v3xctrl_web.routes.camera.subprocess.check_output") as mock_output:
            mock_output.side_effect = OSError("device error")

            response = client.put("/camera/settings/brightness", json={"value": 50})

            assert response.get_json()["error"]["message"] == "Unexpected error"
