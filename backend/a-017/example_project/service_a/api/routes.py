from flask import Blueprint
from ..util import helper_a
from ...shared.helpers import common_helper

api_bp = Blueprint('service_a_api', __name__)

@api_bp.get('/ping')
def ping():
    helper_a()
    return {'service': 'a', 'pong': True, 'common': common_helper()}

