from flask import Blueprint
from ..users import api as users_api

bp = Blueprint('orders', __name__, url_prefix='/orders')

@bp.route('/', methods=['GET'])
def list_orders():
    return 'list orders'

@bp.route('/<int:order_id>', methods=['GET'])
def get_order(order_id):
    return f'order {order_id}'

