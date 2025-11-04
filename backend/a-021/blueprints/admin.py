from flask import Blueprint, jsonify

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
def dashboard():
    return jsonify({
        'message': 'Admin Dashboard',
        'stats': {
            'users': 42,
            'items': 100
        }
    })

@admin_bp.route('/settings')
def settings():
    return jsonify({
        'debug': True,
        'maintenance_mode': False
    })
