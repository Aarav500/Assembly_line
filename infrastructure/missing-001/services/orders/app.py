from flask import Flask, jsonify, request

app = Flask(__name__)

ORDERS = {
    "100": {"order_id": "100", "item": "book", "qty": 1},
    "101": {"order_id": "101", "item": "pen", "qty": 3},
}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "orders"})

@app.route('/', methods=['GET'])
def index():
    return jsonify({"service": "orders", "message": "orders service root"})

@app.route('/', methods=['POST'])
def create_order():
    payload = request.get_json(silent=True) or {}
    item = payload.get('item')
    qty = payload.get('qty', 1)
    if not item:
        return jsonify({"error": "validation_error", "message": "item is required"}), 400
    new_id = str(max([int(i) for i in ORDERS.keys()] + [99]) + 1)
    ORDERS[new_id] = {"order_id": new_id, "item": item, "qty": qty}
    return jsonify(ORDERS[new_id]), 201

@app.route('/<oid>', methods=['GET'])
def get_order(oid):
    o = ORDERS.get(oid)
    if not o:
        return jsonify({"error": "not_found", "message": "order not found"}), 404
    return jsonify(o)

@app.route('/list', methods=['GET'])
def list_orders():
    return jsonify(list(ORDERS.values()))


