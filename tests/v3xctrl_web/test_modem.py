import subprocess
from unittest.mock import patch


class TestModemInfo:
    def test_success(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.return_value = b'{"signal": -70, "operator": "T-Mobile"}'

            response = client.get("/modem/")

            data = response.get_json()["data"]
            assert data["signal"] == -70
            assert data["operator"] == "T-Mobile"

    def test_subprocess_failure(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "v3xctrl-modem-info", output=b"modem not found")

            response = client.get("/modem/")

            error = response.get_json()["error"]
            assert error["message"] == "Fetching modem info failed"
            assert error["details"] == "modem not found"

    def test_subprocess_failure_no_output(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "v3xctrl-modem-info", output=None)

            response = client.get("/modem/")

            assert response.get_json()["error"]["details"] == "No output"


class TestModemReset:
    def test_success(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.return_value = b"OK"

            response = client.post("/modem/reset")

            assert response.status_code == 200
            assert response.get_json()["data"] is None
            assert response.get_json()["error"] is None

    def test_subprocess_failure(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "v3xctrl-modem-reset", output=b"reset failed")

            response = client.post("/modem/reset")

            error = response.get_json()["error"]
            assert error["message"] == "Modem reset failed"
            assert error["details"] == "reset failed"
