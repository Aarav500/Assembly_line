from flask import Blueprint

bp = Blueprint('users', __name__, url_prefix='/users')

@bp.route('/', methods=['GET'])
def list_users():
    return 'list users'

@bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    return f'user {user_id}'

