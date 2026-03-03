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

    def test_timeout(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.TimeoutExpired("v3xctrl-modem-info", 90)

            response = client.get("/modem/")

            error = response.get_json()["error"]
            assert response.status_code == 500
            assert "timed out" in error["message"]

    def test_unexpected_exception(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.side_effect = FileNotFoundError("v3xctrl-modem-info not found")

            response = client.get("/modem/")

            error = response.get_json()["error"]
            assert response.status_code == 500
            assert error["message"] == "Fetching modem info failed"

    def test_invalid_json_output(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.return_value = b"not valid json"

            response = client.get("/modem/")

            assert response.status_code == 500
            assert response.get_json()["error"] is not None


class TestModemModels:
    def test_returns_modem_models(self, client):
        response = client.get("/modem/models")

        assert response.status_code == 200
        data = response.get_json()["data"]
        assert "generic" in data
        assert data["generic"]["validBands"] == [1, 3, 7, 20]
        assert data["generic"]["hasGps"] is False

    def test_returns_all_models(self, client):
        response = client.get("/modem/models")

        data = response.get_json()["data"]
        assert "test-modem" in data
        assert data["test-modem"]["hasGps"] is True


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

    def test_timeout(self, client):
        with patch("v3xctrl_web.routes.modem.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.TimeoutExpired("v3xctrl-modem-reset", 90)

            response = client.post("/modem/reset")

            error = response.get_json()["error"]
            assert response.status_code == 500
            assert "timed out" in error["message"]
