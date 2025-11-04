from flask import Blueprint
from ..util import helper_b
from ...shared.helpers import common_helper

api_bp = Blueprint('service_b_api', __name__)

@api_bp.get('/ping')
def ping():
    helper_b()
    return {'service': 'b', 'pong': True, 'common': common_helper()}
