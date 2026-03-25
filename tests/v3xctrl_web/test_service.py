import subprocess
from unittest.mock import patch


class TestListServices:
    def test_all_services_listed(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.check_output") as mock_output:
            mock_output.return_value = b"Type=simple\nActiveState=active\nResult=success"

            response = client.get("/service/")

            data = response.get_json()["data"]
            assert len(data["services"]) == 10
            for service in data["services"]:
                assert service["type"] == "simple"
                assert service["state"] == "active"
                assert service["result"] == "success"

    def test_service_error_graceful_fallback(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "systemctl")

            response = client.get("/service/")

            data = response.get_json()["data"]
            assert len(data["services"]) == 10
            for service in data["services"]:
                assert service["type"] == "unknown"
                assert service["state"] == "unknown"
                assert service["result"] == "error"

    def test_mixed_service_states(self, client):
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"Type=simple\nActiveState=active\nResult=success"
            raise subprocess.CalledProcessError(1, "systemctl")

        with patch("v3xctrl_web.routes.service.subprocess.check_output", side_effect=side_effect):
            response = client.get("/service/")

            services = response.get_json()["data"]["services"]
            assert services[0]["state"] == "active"
            assert services[1]["state"] == "unknown"


class TestGetService:
    def test_success(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.check_output") as mock_output:
            mock_output.return_value = b"Type=oneshot\nActiveState=inactive\nResult=success"

            response = client.get("/service/v3xctrl-setup-env")

            data = response.get_json()["data"]
            assert data["name"] == "v3xctrl-setup-env"
            assert data["type"] == "oneshot"
            assert data["state"] == "inactive"
            assert data["result"] == "success"

    def test_subprocess_error(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "systemctl")

            response = client.get("/service/nonexistent")

            data = response.get_json()["data"]
            assert data["name"] == "nonexistent"
            assert data["type"] == "unknown"
            assert data["state"] == "unknown"
            assert data["result"] == "error"


class TestStartService:
    def test_success(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.run") as mock_run:
            response = client.post("/service/v3xctrl-video/start")

            assert response.status_code == 200
            assert "Started" in response.get_json()["data"]["message"]
            mock_run.assert_called_once_with(
                ["sudo", "systemctl", "start", "v3xctrl-video"],
                check=True,
                capture_output=True,
                text=True,
            )

    def test_failure(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="unit not found")

            response = client.post("/service/bad-service/start")

            error = response.get_json()["error"]
            assert "Failed to start" in error["message"]
            assert error["details"] == "unit not found"


class TestStopService:
    def test_success(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.run"):
            response = client.post("/service/v3xctrl-video/stop")

            assert response.status_code == 200
            assert "Stopped" in response.get_json()["data"]["message"]

    def test_failure(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="permission denied")

            response = client.post("/service/v3xctrl-video/stop")

            assert "Failed to stop" in response.get_json()["error"]["message"]


class TestRestartService:
    def test_success(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.run"):
            response = client.post("/service/v3xctrl-video/restart")

            assert response.status_code == 200
            assert "Restarted" in response.get_json()["data"]["message"]

    def test_failure(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="timeout")

            response = client.post("/service/v3xctrl-video/restart")

            assert "Failed to restart" in response.get_json()["error"]["message"]


class TestServiceLog:
    def test_success(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.check_output") as mock_output:
            mock_output.return_value = b"Mar 15 10:00:00 host v3xctrl[123]: started"

            response = client.get("/service/v3xctrl-video/log")

            assert response.status_code == 200
            assert "started" in response.get_json()["data"]["log"]
            mock_output.assert_called_once_with(
                ["journalctl", "-n", "50", "--no-page", "-u", "v3xctrl-video"],
                stderr=subprocess.DEVNULL,
            )

    def test_failure(self, client):
        with patch("v3xctrl_web.routes.service.subprocess.check_output") as mock_output:
            mock_output.side_effect = subprocess.CalledProcessError(1, "journalctl")

            response = client.get("/service/v3xctrl-video/log")

            assert "Failed to retrieve log" in response.get_json()["error"]["message"]
