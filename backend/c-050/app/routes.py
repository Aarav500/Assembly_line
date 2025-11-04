from flask import Blueprint, jsonify, request
from .extensions import db
from .models import User, Product, Order
from .services.sample_data import generate_sample_data
from .services.exporter import export_data
from .services.importer import import_data

api_bp = Blueprint('api', __name__)


@api_bp.get('/health')
def health():
    return jsonify({'status': 'ok'})


@api_bp.get('/users')
def list_users():
    users = [u.to_dict() for u in User.query.order_by(User.id.desc()).limit(100)]
    return jsonify({'count': len(users), 'items': users})


@api_bp.get('/products')
def list_products():
    products = [p.to_dict() for p in Product.query.order_by(Product.id.desc()).limit(100)]
    return jsonify({'count': len(products), 'items': products})


@api_bp.get('/orders')
def list_orders():
    orders = [o.to_dict(include_items=True) for o in Order.query.order_by(Order.id.desc()).limit(50)]
    return jsonify({'count': len(orders), 'items': orders})


@api_bp.post('/reset-and-load-sample')
def reset_and_load_sample():
    payload = request.get_json(silent=True) or {}
    users = int(payload.get('users', 10))
    products = int(payload.get('products', 15))
    orders = int(payload.get('orders', 20))
    seed = payload.get('seed')
    stats = generate_sample_data(users=users, products=products, orders=orders, seed=seed)
    return jsonify({'status': 'ok', 'stats': stats})


@api_bp.post('/export')
def export_endpoint():
    payload = request.get_json(silent=True) or {}
    fmt = payload.get('format', 'both')
    out_dir = payload.get('out_dir', 'exports')
    result = export_data(fmt=fmt, out_base=out_dir)
    return jsonify({'status': 'ok', 'result': result})


@api_bp.post('/import')
def import_endpoint():
    payload = request.get_json(silent=True) or {}
    fmt = payload.get('format', 'json')
    from_dir = payload.get('from_dir')
    reset = bool(payload.get('reset', True))
    if not from_dir:
        return jsonify({'status': 'error', 'error': "'from_dir' is required"}), 400
    result = import_data(fmt=fmt, from_dir=from_dir, reset=reset)
    return jsonify({'status': 'ok', 'result': result})

