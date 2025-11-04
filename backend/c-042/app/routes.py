from flask import Blueprint, jsonify, request

from .calculator import clamp, is_palindrome, safe_divide, sign

bp = Blueprint("main", __name__)


@bp.route("/api/divide")
def divide():
    try:
        a = float(request.args.get("a", "0"))
        b = float(request.args.get("b", "1"))
    except ValueError:
        return jsonify(error="invalid numbers"), 400

    default = request.args.get("default")
    default_val = float(default) if default is not None else None

    return jsonify(result=safe_divide(a, b, default=default_val))


@bp.route("/api/clamp")
def clamp_route():
    try:
        n = float(request.args.get("n"))
        lo = float(request.args.get("lo"))
        hi = float(request.args.get("hi"))
    except (TypeError, ValueError):
        return jsonify(error="invalid numbers"), 400

    return jsonify(result=clamp(n, lo, hi))


@bp.route("/api/pal")
def pal():
    s = request.args.get("s", "")
    return jsonify(result=is_palindrome(s))


@bp.route("/api/sign")
def sign_route():
    try:
        n = float(request.args.get("n"))
    except (TypeError, ValueError):
        return jsonify(error="invalid number"), 400
    return jsonify(result=sign(n))

