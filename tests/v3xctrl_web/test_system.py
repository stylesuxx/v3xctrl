import subprocess
from unittest.mock import patch


class TestReboot:
    def test_reboot(self, client):
        with patch("v3xctrl_web.routes.system.subprocess.run") as mock_run:
            response = client.post("/system/reboot")

            assert response.status_code == 200
            assert response.get_json()["data"]["message"] == "Rebooting..."
            mock_run.assert_called_once_with(["sudo", "reboot", "-f"])


class TestShutdown:
    def test_shutdown(self, client):
        with patch("v3xctrl_web.routes.system.subprocess.run") as mock_run:
            response = client.post("/system/shutdown")

            assert response.status_code == 200
            assert response.get_json()["data"]["message"] == "Shutting down..."
            mock_run.assert_called_once_with(["sudo", "poweroff"])


class TestDmesg:
    def test_dmesg_success(self, client):
        with patch("v3xctrl_web.routes.system.subprocess.check_output") as mock_output:
            mock_output.return_value = b"[    0.000000] Booting Linux\n[    1.000000] Ready"

            response = client.get("/system/dmesg")

            assert response.status_code == 200
            assert "Booting Linux" in response.get_json()["data"]["log"]

    def test_dmesg_empty(self, client):
        with patch("v3xctrl_web.routes.system.subprocess.check_output") as mock_output:
            mock_output.return_value = b""

            response = client.get("/system/dmesg")

            assert response.status_code == 200
            assert response.get_json()["data"]["log"] == ""


class TestInfo:
    def test_info_all_packages_found(self, client):
        with (
            patch("v3xctrl_web.routes.system.subprocess.run") as mock_run,
            patch("v3xctrl_web.routes.system.socket.gethostname", return_value="testhost"),
        ):
            mock_result = type("Result", (), {"stdout": "1.2.3"})()
            mock_run.return_value = mock_result

            response = client.get("/system/info")

            data = response.get_json()["data"]
            assert data["hostname"] == "testhost"
            assert data["packages"]["v3xctrl"] == "1.2.3"
            assert data["packages"]["v3xctrl-python"] == "1.2.3"

    def test_info_package_not_found(self, client):
        with (
            patch("v3xctrl_web.routes.system.subprocess.run") as mock_run,
            patch("v3xctrl_web.routes.system.socket.gethostname", return_value="testhost"),
        ):
            mock_run.side_effect = subprocess.CalledProcessError(1, "dpkg-query")

            response = client.get("/system/info")

            data = response.get_json()["data"]
            assert data["hostname"] == "testhost"
            assert data["packages"]["v3xctrl"] is None
            assert data["packages"]["v3xctrl-python"] is None

    def test_info_mixed_packages(self, client):
        def run_side_effect(cmd, **kwargs):
            package = cmd[3]
            if package == "v3xctrl":
                return type("Result", (), {"stdout": "2.0.0"})()
            raise subprocess.CalledProcessError(1, "dpkg-query")

        with (
            patch("v3xctrl_web.routes.system.subprocess.run", side_effect=run_side_effect),
            patch("v3xctrl_web.routes.system.socket.gethostname", return_value="testhost"),
        ):
            response = client.get("/system/info")

            data = response.get_json()["data"]
            assert data["packages"]["v3xctrl"] == "2.0.0"
            assert data["packages"]["v3xctrl-python"] is None
