from flask import jsonify


def index():
    return jsonify({
        "message": "Welcome to the GREEN version",
        "version": "green"
    })


def hello():
    return jsonify({
        "greeting": "Hello from GREEN",
        "version": "green"
    })


def health():
    return jsonify({
        "status": "ok",
        "version": "green"
    })

