import argparse
from flask import Flask, render_template, request, jsonify
import json

app = Flask(__name__, template_folder='templates', static_folder='static')

schema_path = None
config_path = None


@app.route('/')
def index():
    with open(schema_path) as f:
        schema = json.load(f)
    with open(config_path) as f:
        config = json.load(f)

    return render_template('index.html', schema=schema, config=config)


@app.route('/save', methods=['POST'])
def save_config():
    data = request.json
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)

    return jsonify({"message": "Saved"})


def main():
    global schema_path, config_path

    parser = argparse.ArgumentParser(description="Run the Form Editor server.")
    parser.add_argument('--schema', required=True, help='Path to schema.json')
    parser.add_argument('--config', required=True, help='Path to config.json')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', default=5000, type=int, help='Port to run the server on')
    args = parser.parse_args()

    schema_path = args.schema
    config_path = args.config

    app.run(debug=True, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
