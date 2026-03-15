from v3xctrl_web.routes.response import error, success


class TestSuccess:
    def test_default_status(self, app):
        with app.app_context():
            response, status = success({"key": "value"})
            assert status == 200
            data = response.get_json()
            assert data["data"] == {"key": "value"}
            assert data["error"] is None

    def test_custom_status(self, app):
        with app.app_context():
            response, status = success({"created": True}, status=201)
            assert status == 201
            assert response.get_json()["data"] == {"created": True}

    def test_none_data(self, app):
        with app.app_context():
            response, status = success()
            assert status == 200
            data = response.get_json()
            assert data["data"] is None
            assert data["error"] is None


class TestError:
    def test_default_status(self, app):
        with app.app_context():
            response, status = error("something broke")
            assert status == 500
            data = response.get_json()
            assert data["data"] is None
            assert data["error"]["message"] == "something broke"
            assert data["error"]["details"] is None

    def test_with_details(self, app):
        with app.app_context():
            response, _status = error("failed", details="stack trace here")
            data = response.get_json()
            assert data["error"]["details"] == "stack trace here"

    def test_custom_status(self, app):
        with app.app_context():
            _, status = error("bad request", status=400)
            assert status == 400
