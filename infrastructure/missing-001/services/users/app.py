from flask import Flask, jsonify, request
import random

app = Flask(__name__)

# In-memory store
USERS = {
    "1": {"id": "1", "user_name": "alice"},
    "2": {"id": "2", "user_name": "bob"},
}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "users"})

@app.route('/', methods=['GET'])
def root_index():
    return jsonify({"service": "users", "message": "users service root"})

@app.route('/', methods=['POST'])
def create_user():
    payload = request.get_json(silent=True) or {}
    # Expect backend field name user_name
    uname = payload.get('user_name')
    if not uname:
        return jsonify({"error": "validation_error", "message": "user_name is required"}), 400
    new_id = str(max([int(i) for i in USERS.keys()] + [0]) + 1)
    USERS[new_id] = {"id": new_id, "user_name": uname}
    resp = USERS[new_id].copy()
    resp["source"] = "users-backend"
    return jsonify(resp), 201

@app.route('/<uid>', methods=['GET'])
def get_user(uid):
    u = USERS.get(uid)
    if not u:
        return jsonify({"error": "not_found", "message": "user not found"}), 404
    resp = u.copy()
    resp['x_backend'] = 'users'
    return jsonify(resp)

@app.route('/list', methods=['GET'])
def list_users():
    return jsonify(list(USERS.values()))


