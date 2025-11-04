from flask import Blueprint, request, jsonify
from ..db import db
from ..models import Asset, Finding

assets_bp = Blueprint('assets', __name__)


@assets_bp.get("")
def list_assets():
    q = Asset.query
    provider = request.args.get('provider')
    if provider:
        q = q.filter(Asset.provider == provider)
    region = request.args.get('region')
    if region:
        q = q.filter(Asset.region == region)
    assets = q.order_by(Asset.created_at.desc()).all()
    return jsonify([a.to_dict() for a in assets])


@assets_bp.get("/<asset_id>")
def get_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    return jsonify(asset.to_dict())


@assets_bp.get("/<asset_id>/findings")
def get_asset_findings(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    state = request.args.get('state')
    status = request.args.get('status')
    q = Finding.query.filter(Finding.asset_id == asset.id)
    if state:
        q = q.filter(Finding.state == state)
    if status:
        q = q.filter(Finding.status == status)
    return jsonify([f.to_dict() for f in q.all()])


@assets_bp.post("")
def create_asset():
    data = request.get_json(force=True)
    required = ['name', 'type', 'provider']
    for r in required:
        if r not in data:
            return jsonify({'error': f'missing_field:{r}'}), 400
    asset = Asset(
        name=data['name'],
        type=data['type'],
        provider=data['provider'],
        region=data.get('region'),
        tags=data.get('tags') or {}
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify(asset.to_dict()), 201

