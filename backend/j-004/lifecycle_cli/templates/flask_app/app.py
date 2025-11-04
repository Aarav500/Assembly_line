import argparse
from flask import Flask, jsonify, request

app = Flask("{{APP_NAME}}")


@app.route("/", methods=["GET"])  # Home route
def home():
    return jsonify({"message": "Welcome to {{APP_NAME}}!"})


@app.route("/health", methods=["GET"])  # Health check
def health():
    return jsonify({"status": "ok"})


@app.route("/echo", methods=["POST"])  # Echo endpoint
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify({"you_sent": data})


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Flask app")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)

