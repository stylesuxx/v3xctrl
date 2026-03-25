import subprocess
from unittest.mock import patch

import pytest


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


class TestLogArchives:
    @pytest.fixture()
    def journal_directory(self, tmp_path):
        with patch("v3xctrl_web.routes.system.JOURNAL_DIR", tmp_path):
            yield tmp_path

    def test_list_archives(self, client, journal_directory):
        (journal_directory / "archive_1.tar.gz").write_bytes(b"x" * 100)
        (journal_directory / "archive_2.tar.gz").write_bytes(b"x" * 200)

        response = client.get("/system/logs")

        assert response.status_code == 200
        archives = response.get_json()["data"]["archives"]
        assert len(archives) == 2
        assert archives[0]["name"] == "archive_2.tar.gz"
        assert archives[0]["size"] == 200
        assert archives[1]["name"] == "archive_1.tar.gz"
        assert archives[1]["size"] == 100

    def test_list_archives_empty_directory(self, client, journal_directory):
        response = client.get("/system/logs")

        assert response.status_code == 200
        archives = response.get_json()["data"]["archives"]
        assert archives == []

    def test_list_archives_ignores_non_archive_files(self, client, journal_directory):
        (journal_directory / "archive_1.tar.gz").write_bytes(b"x" * 100)
        (journal_directory / "current-dmesg").write_text("some log")
        (journal_directory / "random.txt").write_text("noise")

        response = client.get("/system/logs")

        assert response.status_code == 200
        archives = response.get_json()["data"]["archives"]
        assert len(archives) == 1
        assert archives[0]["name"] == "archive_1.tar.gz"

    def test_list_archives_directory_missing(self, client):
        with patch("v3xctrl_web.routes.system.JOURNAL_DIR") as mock_dir:
            mock_dir.exists.return_value = False

            response = client.get("/system/logs")

            assert response.status_code == 200
            assert response.get_json()["data"]["archives"] == []


class TestLogArchiveDownload:
    @pytest.fixture()
    def journal_directory(self, tmp_path):
        with patch("v3xctrl_web.routes.system.JOURNAL_DIR", tmp_path):
            yield tmp_path

    def test_download_archive(self, client, journal_directory):
        content = b"\x1f\x8b" + b"\x00" * 50
        (journal_directory / "archive_1.tar.gz").write_bytes(content)

        response = client.get("/system/logs/archive_1.tar.gz")

        assert response.status_code == 200
        assert response.data == content

    def test_download_invalid_filename_no_prefix(self, client, journal_directory):
        (journal_directory / "evil.tar.gz").write_bytes(b"data")

        response = client.get("/system/logs/evil.tar.gz")

        assert response.status_code == 400

    def test_download_invalid_filename_no_suffix(self, client, journal_directory):
        (journal_directory / "archive_1.txt").write_bytes(b"data")

        response = client.get("/system/logs/archive_1.txt")

        assert response.status_code == 400

    def test_download_nonexistent_archive(self, client, journal_directory):
        response = client.get("/system/logs/archive_999.tar.gz")

        assert response.status_code == 404


class TestLogArchiveDelete:
    @pytest.fixture()
    def journal_directory(self, tmp_path):
        with patch("v3xctrl_web.routes.system.JOURNAL_DIR", tmp_path):
            yield tmp_path

    def test_delete_archive(self, client, journal_directory):
        archive = journal_directory / "archive_1.tar.gz"
        archive.write_bytes(b"x" * 100)

        response = client.delete("/system/logs/archive_1.tar.gz")

        assert response.status_code == 200
        assert not archive.exists()

    def test_delete_invalid_filename_no_prefix(self, client, journal_directory):
        (journal_directory / "evil.tar.gz").write_bytes(b"data")

        response = client.delete("/system/logs/evil.tar.gz")

        assert response.status_code == 400
        assert (journal_directory / "evil.tar.gz").exists()

    def test_delete_invalid_filename_no_suffix(self, client, journal_directory):
        (journal_directory / "archive_1.txt").write_bytes(b"data")

        response = client.delete("/system/logs/archive_1.txt")

        assert response.status_code == 400

    def test_delete_nonexistent_archive(self, client, journal_directory):
        response = client.delete("/system/logs/archive_999.tar.gz")

        assert response.status_code == 404
