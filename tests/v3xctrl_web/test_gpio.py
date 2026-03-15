from unittest.mock import MagicMock, patch


class TestPwm:
    def test_set_pwm(self, client):
        mock_pwm_instance = MagicMock()
        with patch("v3xctrl_web.routes.gpio.HardwarePWM", return_value=mock_pwm_instance) as mock_class:
            response = client.put("/gpio/0/pwm", json={"value": 1500})

            assert response.status_code == 200
            data = response.get_json()["data"]
            assert data["gpio"] == 0
            assert data["value"] == 1500
            mock_class.assert_called_once_with(0)
            mock_pwm_instance.setup.assert_called_once_with(1500)

    def test_missing_value(self, client):
        response = client.put("/gpio/0/pwm", json={})

        assert response.status_code == 400
        error = response.get_json()["error"]
        assert "'value' is required" in error["message"]

    def test_no_content_type(self, client):
        response = client.put("/gpio/0/pwm")

        assert response.status_code == 415

    def test_different_channel(self, client):
        mock_pwm_instance = MagicMock()
        with patch("v3xctrl_web.routes.gpio.HardwarePWM", return_value=mock_pwm_instance) as mock_class:
            response = client.put("/gpio/2/pwm", json={"value": 500})

            data = response.get_json()["data"]
            assert data["gpio"] == 2
            assert data["value"] == 500
            mock_class.assert_called_once_with(2)
