from flask import jsonify


def index():
    return jsonify({
        "message": "Welcome to the BLUE version",
        "version": "blue"
    })


def hello():
    return jsonify({
        "greeting": "Hello from BLUE",
        "version": "blue"
    })


def health():
    return jsonify({
        "status": "ok",
        "version": "blue"
    })

