import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime
from flask import Flask, request, jsonify, abort

from config import Config
from db import get_session, engine
from models import Base, Migration, Approval
from safety_checks import analyze
from executor import dry_run as exec_dry_run, apply as exec_apply

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Initialize DB schema
with engine.begin() as conn:
    Base.metadata.create_all(bind=conn)


def required_roles_for_env(env: str):
    return Config.REQUIRED_ROLES.get(env, ["owner"])


def dialect_for_env(env: str):
    return Config.DIALECT_BY_ENV.get(env, 'postgresql')


def can_transition_to_approved(mig: Migration):
    roles_required = set(required_roles_for_env(mig.target_env))
    roles_present = set(a.role for a in mig.approvals)
    has_errors = any(i.get('severity') == 'error' for i in mig.get_issues())
    return (roles_required.issubset(roles_present)) and not has_errors

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/migrations', methods=['POST'])
def create_migration():
    data = request.get_json(force=True, silent=False) or {}
    title = data.get('title')
    sql = data.get('sql')
    target_env = (data.get('target_env') or 'dev').lower()
    if not title or not sql:
        abort(400, 'title and sql are required')
    if target_env not in Config.TARGET_DBS:
        abort(400, f"target_env must be one of: {', '.join(Config.TARGET_DBS.keys())}")

    description = data.get('description')
    created_by = data.get('created_by')

    issues = analyze(sql, dialect=dialect_for_env(target_env))
    status = 'needs_approval'
    if any(i.get('severity') == 'error' for i in issues):
        status = 'blocked'

    with get_session() as session:
        mig = Migration(
            title=title,
            description=description,
            created_by=created_by,
            target_env=target_env,
            sql=sql,
            status=status,
        )
        session.add(mig)
        session.flush()  # assign id
        mig.set_issues(issues)
        # persist SQL to file for auditability
        try:
            with open(mig.sql_file_path(), 'w', encoding='utf-8') as f:
                f.write(sql)
        except Exception:
            pass
        session.add(mig)
        result = mig.to_dict()
    return jsonify(result), 201

@app.route('/migrations', methods=['GET'])
def list_migrations():
    q_status = request.args.get('status')
    with get_session() as session:
        query = session.query(Migration).order_by(Migration.created_at.desc())
        if q_status:
            query = query.filter(Migration.status == q_status)
        items = [m.to_dict(include_sql=False) for m in query.all()]
    return jsonify({"migrations": items})

@app.route('/migrations/<int:mig_id>', methods=['GET'])
def get_migration(mig_id):
    with get_session() as session:
        mig = session.get(Migration, mig_id)
        if not mig:
            abort(404, 'Migration not found')
        return jsonify(mig.to_dict())

@app.route('/migrations/<int:mig_id>/issues', methods=['GET'])
def get_migration_issues(mig_id):
    with get_session() as session:
        mig = session.get(Migration, mig_id)
        if not mig:
            abort(404, 'Migration not found')
        return jsonify({"issues": mig.get_issues()})

@app.route('/migrations/<int:mig_id>/dry-run', methods=['POST'])
def dry_run_migration(mig_id):
    with get_session() as session:
        mig = session.get(Migration, mig_id)
        if not mig:
            abort(404, 'Migration not found')
        success, log = exec_dry_run(mig.sql, mig.target_env)
        mig.dry_run_status = 'success' if success else 'failed'
        mig.dry_run_log = log
        # if no blocking issues and approvals ready, mark approved
        if can_transition_to_approved(mig):
            mig.status = 'approved'
        session.add(mig)
        resp = mig.to_dict()
    return jsonify(resp)

@app.route('/migrations/<int:mig_id>/approvals', methods=['POST'])
def approve_migration(mig_id):
    data = request.get_json(force=True, silent=False) or {}
    user = data.get('user')
    role = (data.get('role') or '').lower()
    comment = data.get('comment')
    if not user or not role:
        abort(400, 'user and role are required')

    with get_session() as session:
        mig = session.get(Migration, mig_id)
        if not mig:
            abort(404, 'Migration not found')
        if mig.status == 'applied':
            abort(400, 'Migration already applied')

        if role not in required_roles_for_env(mig.target_env):
            abort(400, f"Role '{role}' is not required for env '{mig.target_env}'. Required: {required_roles_for_env(mig.target_env)}")

        # prevent duplicate user+role for same migration
        existing = [a for a in mig.approvals if a.user == user and a.role == role]
        if existing:
            abort(400, 'This user has already approved with this role')

        approval = Approval(migration_id=mig.id, user=user, role=role, comment=comment)
        session.add(approval)
        session.flush()

        # Transition state when approvals satisfied & no blocking issues
        if can_transition_to_approved(mig):
            mig.status = 'approved'
        elif mig.status == 'blocked':
            # keep blocked unless issues removed
            pass
        else:
            mig.status = 'needs_approval'
        session.add(mig)
        resp = mig.to_dict()
    return jsonify(resp), 201

@app.route('/migrations/<int:mig_id>/apply', methods=['POST'])
def apply_migration(mig_id):
    with get_session() as session:
        mig = session.get(Migration, mig_id)
        if not mig:
            abort(404, 'Migration not found')
        if mig.apply_status == 'success' or mig.status == 'applied':
            abort(400, 'Migration already applied')
        # Preconditions
        issues = mig.get_issues()
        if any(i.get('severity') == 'error' for i in issues):
            abort(400, 'Migration has blocking issues. Resolve them before applying.')
        roles_required = set(required_roles_for_env(mig.target_env))
        roles_present = set(a.role for a in mig.approvals)
        if not roles_required.issubset(roles_present):
            abort(400, f"Missing required approvals: {sorted(roles_required - roles_present)}")
        if mig.dry_run_status != 'success':
            abort(400, 'Dry-run must succeed before applying migration')

        success, log = exec_apply(mig.sql, mig.target_env)
        mig.apply_status = 'success' if success else 'failed'
        mig.apply_log = log
        if success:
            mig.status = 'applied'
            mig.applied_at = datetime.utcnow()
        else:
            mig.status = 'failed'
        session.add(mig)
        resp = mig.to_dict()
    return jsonify(resp)

@app.route('/migrations/<int:mig_id>/recheck', methods=['POST'])
def recheck_migration(mig_id):
    # Re-run static safety checks (e.g., after editing SQL via file)
    with get_session() as session:
        mig = session.get(Migration, mig_id)
        if not mig:
            abort(404, 'Migration not found')
        issues = analyze(mig.sql, dialect=dialect_for_env(mig.target_env))
        mig.set_issues(issues)
        # update status based on issues and approvals
        if any(i.get('severity') == 'error' for i in issues):
            mig.status = 'blocked'
        else:
            if can_transition_to_approved(mig):
                mig.status = 'approved'
            else:
                mig.status = 'needs_approval'
        session.add(mig)
        return jsonify(mig.to_dict())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



def create_app():
    return app
