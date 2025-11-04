import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

users = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
]

@app.route('/')
def index():
    return jsonify({"message": "Mock Server API"})

@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(users)

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    new_user = {
        "id": len(users) + 1,
        "name": data.get("name"),
        "email": data.get("email")
    }
    users.append(new_user)
    return jsonify(new_user), 201

if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app


@app.route('/users/1', methods=['GET'])
def _auto_stub_users_1():
    return 'Auto-generated stub for /users/1', 200


@app.route('/users/999', methods=['GET'])
def _auto_stub_users_999():
    return 'Auto-generated stub for /users/999', 200


@app.route('/api/users/1', methods=['GET'])
def _auto_stub_api_users_1():
    return 'Auto-generated stub for /api/users/1', 200
