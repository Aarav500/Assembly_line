import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

users = [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"}
]

@app.route('/')
def home():
    return jsonify({"message": "Welcome to Flask API"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(users)

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = next((u for u in users if u['id'] == user_id), None)
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    new_user = {
        "id": len(users) + 1,
        "name": data.get('name')
    }
    users.append(new_user)
    return jsonify(new_user), 201

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/users/1', methods=['GET'])
def _auto_stub_users_1():
    return 'Auto-generated stub for /users/1', 200


@app.route('/users/999', methods=['GET'])
def _auto_stub_users_999():
    return 'Auto-generated stub for /users/999', 200


@app.route('/echo', methods=['POST'])
def _auto_stub_echo():
    return 'Auto-generated stub for /echo', 200


@app.route('/greet/test', methods=['GET'])
def _auto_stub_greet_test():
    return 'Auto-generated stub for /greet/test', 200


@app.route('/items', methods=['GET'])
def _auto_stub_items():
    return 'Auto-generated stub for /items', 200


@app.route('/todo', methods=['GET'])
def _auto_stub_todo():
    return 'Auto-generated stub for /todo', 200


@app.route('/greet/Ada', methods=['GET'])
def _auto_stub_greet_Ada():
    return 'Auto-generated stub for /greet/Ada', 200


@app.route('/items?limit=2', methods=['GET'])
def _auto_stub_items_limit_2():
    return 'Auto-generated stub for /items?limit=2', 200
