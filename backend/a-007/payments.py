from flask import Blueprint, request, jsonify
from uuid import uuid4


payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payments_bp.route("/checkout", methods=["POST"])
def checkout():
    try:
        data = request.get_json(silent=True) or {}
        amount = data.get("amount")
        currency = data.get("currency", "USD")
        if amount is None:
            return jsonify({"error": "amount required"}), 400
        # demo only: pretend to create a payment intent/charge
        payment_id = str(uuid4())
        return jsonify({
            "ok": True,
            "payment_id": payment_id,
            "status": "authorized",
            "amount": amount,
            "currency": currency,
        })
    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500