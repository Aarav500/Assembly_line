from flask import request, jsonify
from sqlalchemy import or_
from db import db
from models import Dataset
from . import api

@api.route('/datasets', methods=['POST'])
def create_dataset():
    payload = request.get_json(force=True) or {}
    name = payload.get('name')
    if not name:
        return jsonify({'error': 'name is required'}), 400
    if Dataset.query.filter_by(name=name).first():
        return jsonify({'error': f"dataset '{name}' already exists"}), 409
    ds = Dataset(
        name=name,
        uri=payload.get('uri'),
        description=payload.get('description'),
        sha256=payload.get('sha256'),
        metadata=payload.get('metadata'),
    )
    db.session.add(ds)
    db.session.commit()
    return jsonify(ds.to_dict()), 201

@api.route('/datasets', methods=['GET'])
def list_datasets():
    q = request.args.get('q')
    query = Dataset.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Dataset.name.ilike(like), Dataset.description.ilike(like)))
    datasets = query.order_by(Dataset.created_at.desc()).all()
    return jsonify([d.to_dict() for d in datasets])

@api.route('/datasets/<int:dataset_id>', methods=['GET'])
def get_dataset(dataset_id):
    ds = Dataset.query.get_or_404(dataset_id)
    return jsonify(ds.to_dict())

@api.route('/datasets/<int:dataset_id>', methods=['PATCH'])
def update_dataset(dataset_id):
    ds = Dataset.query.get_or_404(dataset_id)
    payload = request.get_json(force=True) or {}
    if 'name' in payload:
        new_name = payload['name']
        if new_name != ds.name and Dataset.query.filter_by(name=new_name).first():
            return jsonify({'error': 'name already exists'}), 409
        ds.name = new_name
    if 'uri' in payload:
        ds.uri = payload['uri']
    if 'description' in payload:
        ds.description = payload['description']
    if 'sha256' in payload:
        ds.sha256 = payload['sha256']
    if 'metadata' in payload:
        ds.metadata = payload['metadata']
    db.session.commit()
    return jsonify(ds.to_dict())

