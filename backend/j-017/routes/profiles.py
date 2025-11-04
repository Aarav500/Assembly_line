from flask import Blueprint, request, jsonify
from database import db
from models import Profile

profiles_bp = Blueprint('profiles', __name__, url_prefix='/profiles')


def _parse_profile_payload(payload):
    fields = [
        'name', 'description', 'temperature', 'top_p', 'presence_penalty',
        'frequency_penalty', 'max_tokens', 'top_k', 'seed'
    ]
    data = {}
    for f in fields:
        if f in payload:
            data[f] = payload[f]
    return data


@profiles_bp.get('')
def list_profiles():
    items = Profile.query.order_by(Profile.id.asc()).all()
    return jsonify([p.to_dict() for p in items])


@profiles_bp.post('')
def create_profile():
    payload = request.get_json(force=True) or {}
    data = _parse_profile_payload(payload)

    if not data.get('name'):
        return jsonify({"error": "name is required"}), 400

    if Profile.query.filter_by(name=data['name']).first():
        return jsonify({"error": "profile with this name already exists"}), 400

    p = Profile(**data)
    db.session.add(p)
    db.session.commit()

    return jsonify(p.to_dict()), 201


@profiles_bp.get('/<int:profile_id>')
def get_profile(profile_id):
    p = Profile.query.get_or_404(profile_id)
    return jsonify(p.to_dict())


@profiles_bp.put('/<int:profile_id>')
def update_profile(profile_id):
    p = Profile.query.get_or_404(profile_id)
    payload = request.get_json(force=True) or {}
    data = _parse_profile_payload(payload)

    rename = data.get('name')
    if rename and rename != p.name:
        if Profile.query.filter(Profile.name == rename, Profile.id != profile_id).first():
            return jsonify({"error": "another profile with this name exists"}), 400

    for k, v in data.items():
        setattr(p, k, v)
    db.session.commit()

    return jsonify(p.to_dict())


@profiles_bp.delete('/<int:profile_id>')
def delete_profile(profile_id):
    p = Profile.query.get_or_404(profile_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"status": "deleted", "id": profile_id})

