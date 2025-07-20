import argparse
from flask import Flask, render_template
from flask_smorest import Api
import json

from routes import register_routes


def create_app(schema_path, config_path):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['SCHEMA_PATH'] = schema_path
    app.config['CONFIG_PATH'] = config_path

    # Flask-smorest OpenAPI config
    app.config['API_TITLE'] = 'V3XCTRL API'
    app.config['API_VERSION'] = 'v1'
    app.config['OPENAPI_VERSION'] = '3.0.2'
    app.config['OPENAPI_URL_PREFIX'] = '/'
    app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger'
    app.config['OPENAPI_SWAGGER_UI_URL'] = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'

    api = Api(app)
    register_routes(api)

    @app.route('/')
    def index():
        with open(schema_path) as f:
            schema = json.load(f)
        with open(config_path) as f:
            config = json.load(f)

        return render_template('index.html', schema=schema, config=config)

    return app


def main():
    global schema_path, config_path

    parser = argparse.ArgumentParser(description="Run the Form Editor server.")
    parser.add_argument('--schema', required=True, help='Path to schema.json')
    parser.add_argument('--config', required=True, help='Path to config.json')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', default=5000, type=int, help='Port to run the server on')
    args = parser.parse_args()

    app = create_app(args.schema, args.config)
    app.run(debug=True, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
