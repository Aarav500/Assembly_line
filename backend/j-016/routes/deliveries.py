from flask import Blueprint, request, jsonify
from models import Delivery

bp = Blueprint('deliveries', __name__)

@bp.route('/deliveries', methods=['GET'])
def list_deliveries():
    team_id = request.args.get('team_id')
    status = request.args.get('status')
    q = Delivery.query
    if team_id:
        q = q.filter(Delivery.team_id == int(team_id))
    if status:
        q = q.filter(Delivery.status == status)
    q = q.order_by(Delivery.id.desc()).limit(int(request.args.get('limit', '100')))
    items = q.all()
    return jsonify([d.to_dict() for d in items])

