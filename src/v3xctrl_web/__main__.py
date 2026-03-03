import argparse
from pathlib import Path

from flask import Flask, Response, send_from_directory
from flask_compress import Compress
from flask_cors import CORS
from flask_smorest import Api

from .routes import register_routes

PACKAGE_DIR = Path(__file__).resolve().parent
DIST_DIR = PACKAGE_DIR / "dist"


def create_app(schema_path: str, config_path: str, modems_path: str) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(DIST_DIR),
        static_url_path="",
    )
    Compress(app)
    CORS(app)
    app.config["SCHEMA_PATH"] = schema_path
    app.config["CONFIG_PATH"] = config_path
    app.config["MODEMS_PATH"] = modems_path

    # Flask-smorest OpenAPI config
    app.config["API_TITLE"] = "V3XCTRL API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "/swagger-ui/"

    api = Api(app)
    register_routes(api)

    @app.route("/")
    def index() -> Response:
        return send_from_directory(str(DIST_DIR), "index.html")

    @app.route("/swagger-ui/<path:filename>")
    def swagger_ui(filename: str) -> Response:
        return send_from_directory(str(DIST_DIR / "swagger-ui"), filename)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Form Editor server.")
    parser.add_argument("--schema", required=True, help="Path to schema.json")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--modems", required=True, help="Path to modems.json")
    parser.add_argument("--host", default="0.0.0.0", help="Host to run the server on")
    parser.add_argument("--port", default=80, type=int, help="Port to run the server on")
    args = parser.parse_args()

    app = create_app(args.schema, args.config, args.modems)
    app.run(debug=False, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
