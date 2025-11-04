import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime
from flask import Flask, request, jsonify, g
from database import db
from models import User, Stage, Gate, GateAllowedUser, Deployment, GateApproval, AuditLog
from auth import require_auth, require_admin, generate_api_key
from utils import audit, get_first_stage, get_next_stage, user_allowed_on_gate, stage_ready_for_advance


def create_app():
    app = Flask(__name__)

    db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'})

    @app.route('/bootstrap-admin', methods=['POST'])
    def bootstrap_admin():
        # Allow creating an initial admin only if no users exist
        if User.query.count() > 0:
            return jsonify({'error': 'Users already exist'}), 400
        data = request.get_json(force=True, silent=True) or {}
        name = data.get('name') or 'Admin'
        email = data.get('email') or 'admin@example.com'
        api_key = generate_api_key()
        user = User(name=name, email=email, role='admin', api_key=api_key, active=True)
        db.session.add(user)
        audit(None, 'bootstrap_admin', 'user', None, {'email': email})
        db.session.commit()
        return jsonify({'message': 'Admin created', 'user': user.to_dict(), 'api_key': api_key})

    @app.route('/users', methods=['POST'])
    @require_admin
    def create_user():
        data = request.get_json(force=True, silent=True) or {}
        name = data.get('name')
        email = data.get('email')
        role = data.get('role', 'user')
        if not name or not email:
            return jsonify({'error': 'name and email are required'}), 400
        if role not in ('admin', 'approver', 'user'):
            return jsonify({'error': 'invalid role'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'email already exists'}), 400
        api_key = generate_api_key()
        user = User(name=name, email=email, role=role, api_key=api_key, active=True)
        db.session.add(user)
        audit(g.current_user.id, 'create', 'user', None, {'email': email, 'role': role})
        db.session.commit()
        return jsonify({'message': 'User created', 'user': user.to_dict(), 'api_key': api_key})

    @app.route('/users', methods=['GET'])
    @require_admin
    def list_users():
        users = User.query.all()
        return jsonify({'users': [u.to_dict() for u in users]})

    @app.route('/stages', methods=['POST'])
    @require_admin
    def create_stage():
        data = request.get_json(force=True, silent=True) or {}
        name = data.get('name')
        position = data.get('position')
        if not name:
            return jsonify({'error': 'name is required'}), 400
        if position is None:
            max_pos = db.session.query(db.func.max(Stage.position)).scalar()
            position = (max_pos or 0) + 1
        else:
            if Stage.query.filter_by(position=position).first():
                return jsonify({'error': 'position already in use'}), 400
        stage = Stage(name=name, position=position)
        db.session.add(stage)
        db.session.flush()
        audit(g.current_user.id, 'create', 'stage', stage.id, {'name': name, 'position': position})
        db.session.commit()
        return jsonify({'stage': stage.to_dict()})

    @app.route('/stages', methods=['GET'])
    @require_auth
    def list_stages():
        stages = Stage.query.order_by(Stage.position.asc()).all()
        return jsonify({'stages': [s.to_dict(with_gates=True) for s in stages]})

    @app.route('/gates', methods=['POST'])
    @require_admin
    def create_gate():
        data = request.get_json(force=True, silent=True) or {}
        stage_id = data.get('stage_id')
        name = data.get('name')
        description = data.get('description')
        required_approvals = data.get('required_approvals', 1)
        allow_roles = data.get('allow_roles', [])
        allow_user_ids = data.get('allow_user_ids', [])
        if not stage_id or not name:
            return jsonify({'error': 'stage_id and name are required'}), 400
        stage = Stage.query.get(stage_id)
        if not stage:
            return jsonify({'error': 'stage not found'}), 404
        if not isinstance(required_approvals, int) or required_approvals < 1:
            return jsonify({'error': 'required_approvals must be >= 1'}), 400
        if not isinstance(allow_roles, list) or not all(isinstance(r, str) for r in allow_roles):
            return jsonify({'error': 'allow_roles must be a list of strings'}), 400
        if not isinstance(allow_user_ids, list) or not all(isinstance(uid, int) for uid in allow_user_ids):
            return jsonify({'error': 'allow_user_ids must be a list of user ids'}), 400
        gate = Gate(stage_id=stage_id, name=name, description=description, required_approvals=required_approvals, allow_roles=','.join(allow_roles), created_by=g.current_user.id)
        db.session.add(gate)
        db.session.flush()
        for uid in allow_user_ids:
            if not User.query.get(uid):
                db.session.rollback()
                return jsonify({'error': f'user id {uid} not found'}), 400
            db.session.add(GateAllowedUser(gate_id=gate.id, user_id=uid))
        audit(g.current_user.id, 'create', 'gate', gate.id, {'stage_id': stage_id, 'name': name, 'required_approvals': required_approvals, 'allow_roles': allow_roles, 'allow_user_ids': allow_user_ids})
        db.session.commit()
        return jsonify({'gate': gate.to_dict(include_allowed=True)})

    @app.route('/gates', methods=['GET'])
    @require_auth
    def list_gates():
        stage_id = request.args.get('stage_id', type=int)
        q = Gate.query
        if stage_id:
            q = q.filter_by(stage_id=stage_id)
        gates = q.all()
        return jsonify({'gates': [g.to_dict(include_allowed=True) for g in gates]})

    @app.route('/deployments', methods=['POST'])
    @require_auth
    def create_deployment():
        data = request.get_json(force=True, silent=True) or {}
        version = data.get('version')
        description = data.get('description')
        if not version:
            return jsonify({'error': 'version is required'}), 400
        first_stage = get_first_stage()
        if not first_stage:
            return jsonify({'error': 'No stages configured'}), 400
        dep = Deployment(version=version, description=description, status='pending', current_stage_id=first_stage.id, created_by=g.current_user.id)
        db.session.add(dep)
        db.session.flush()
        audit(g.current_user.id, 'create', 'deployment', dep.id, {'version': version})
        db.session.commit()
        return jsonify({'deployment': dep.to_dict(include_details=True)})

    @app.route('/deployments', methods=['GET'])
    @require_auth
    def list_deployments():
        deployments = Deployment.query.order_by(Deployment.created_at.desc()).all()
        return jsonify({'deployments': [d.to_dict(include_details=True) for d in deployments]})

    @app.route('/deployments/<int:dep_id>', methods=['GET'])
    @require_auth
    def get_deployment(dep_id):
        dep = Deployment.query.get(dep_id)
        if not dep:
            return jsonify({'error': 'deployment not found'}), 404
        # augment with gate readiness summary
        stage = dep.current_stage
        summary = {}
        ready = False
        if stage:
            ready, summary = stage_ready_for_advance(dep, stage)
        return jsonify({'deployment': dep.to_dict(include_details=True), 'stage_ready': ready, 'gates_summary': summary})

    @app.route('/deployments/<int:dep_id>/approve', methods=['POST'])
    @require_auth
    def approve_gate(dep_id):
        dep = Deployment.query.get(dep_id)
        if not dep:
            return jsonify({'error': 'deployment not found'}), 404
        data = request.get_json(force=True, silent=True) or {}
        gate_id = data.get('gate_id')
        decision = data.get('decision', 'approved')
        comment = data.get('comment')
        if not gate_id:
            return jsonify({'error': 'gate_id is required'}), 400
        gate = Gate.query.get(gate_id)
        if not gate:
            return jsonify({'error': 'gate not found'}), 404
        if not dep.current_stage_id or gate.stage_id != dep.current_stage_id:
            return jsonify({'error': 'gate does not belong to the current stage'}), 400
        if not user_allowed_on_gate(g.current_user, gate):
            return jsonify({'error': 'user not allowed to approve this gate'}), 403
        if decision not in ('approved', 'rejected'):
            return jsonify({'error': 'decision must be approved or rejected'}), 400
        approval = GateApproval.query.filter_by(deployment_id=dep.id, gate_id=gate.id, approver_id=g.current_user.id).first()
        if not approval:
            approval = GateApproval(deployment_id=dep.id, gate_id=gate.id, approver_id=g.current_user.id, decision=decision, comment=comment)
            db.session.add(approval)
        else:
            approval.decision = decision
            approval.comment = comment
        dep.status = 'in_progress' if decision == 'approved' else 'blocked'
        audit(g.current_user.id, 'gate_approval', 'deployment', dep.id, {'gate_id': gate.id, 'decision': decision, 'comment': comment})
        db.session.commit()
        return jsonify({'message': 'recorded', 'approval': approval.to_dict()})

    @app.route('/deployments/<int:dep_id>/revoke-approval', methods=['POST'])
    @require_auth
    def revoke_approval(dep_id):
        dep = Deployment.query.get(dep_id)
        if not dep:
            return jsonify({'error': 'deployment not found'}), 404
        data = request.get_json(force=True, silent=True) or {}
        gate_id = data.get('gate_id')
        if not gate_id:
            return jsonify({'error': 'gate_id is required'}), 400
        approval = GateApproval.query.filter_by(deployment_id=dep.id, gate_id=gate_id, approver_id=g.current_user.id).first()
        if not approval:
            return jsonify({'error': 'no approval found to revoke'}), 404
        db.session.delete(approval)
        # Update status if needed
        dep.status = 'pending'
        audit(g.current_user.id, 'gate_approval_revoke', 'deployment', dep.id, {'gate_id': gate_id})
        db.session.commit()
        return jsonify({'message': 'revoked'})

    @app.route('/deployments/<int:dep_id>/reset-gate', methods=['POST'])
    @require_admin
    def reset_gate(dep_id):
        dep = Deployment.query.get(dep_id)
        if not dep:
            return jsonify({'error': 'deployment not found'}), 404
        data = request.get_json(force=True, silent=True) or {}
        gate_id = data.get('gate_id')
        if not gate_id:
            return jsonify({'error': 'gate_id is required'}), 400
        deleted = GateApproval.query.filter_by(deployment_id=dep.id, gate_id=gate_id).delete()
        dep.status = 'pending'
        audit(g.current_user.id, 'gate_reset', 'deployment', dep.id, {'gate_id': gate_id, 'deleted': deleted})
        db.session.commit()
        return jsonify({'message': 'gate approvals reset', 'deleted': deleted})

    @app.route('/deployments/<int:dep_id>/advance', methods=['POST'])
    @require_auth
    def advance_deployment(dep_id):
        dep = Deployment.query.get(dep_id)
        if not dep:
            return jsonify({'error': 'deployment not found'}), 404
        if not dep.current_stage:
            return jsonify({'error': 'deployment has no current stage'}), 400
        ready, detail = stage_ready_for_advance(dep, dep.current_stage)
        if not ready:
            audit(g.current_user.id, 'advance_blocked', 'deployment', dep.id, {'stage_id': dep.current_stage.id, 'details': detail})
            return jsonify({'error': 'not all gates satisfied', 'gates_summary': detail}), 400
        next_stage = get_next_stage(dep.current_stage_id)
        if next_stage:
            dep.current_stage_id = next_stage.id
            dep.status = 'in_progress'
            audit(g.current_user.id, 'advance_stage', 'deployment', dep.id, {'from_stage_id': dep.current_stage.id, 'to_stage_id': next_stage.id})
        else:
            dep.current_stage_id = None
            dep.status = 'completed'
            audit(g.current_user.id, 'complete_deployment', 'deployment', dep.id, {'completed_at': datetime.utcnow().isoformat() + 'Z'})
        db.session.commit()
        return jsonify({'deployment': dep.to_dict(include_details=True)})

    @app.route('/audit-logs', methods=['GET'])
    @require_admin
    def list_audit_logs():
        q = AuditLog.query.order_by(AuditLog.created_at.desc())
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id', type=int)
        actor_id = request.args.get('actor_id', type=int)
        if entity_type:
            q = q.filter_by(entity_type=entity_type)
        if entity_id is not None:
            q = q.filter_by(entity_id=entity_id)
        if actor_id is not None:
            q = q.filter_by(actor_id=actor_id)
        logs = q.limit(500).all()
        return jsonify({'logs': [l.to_dict() for l in logs]})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

