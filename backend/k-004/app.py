import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Flask, request, jsonify, render_template, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
from apscheduler.schedulers.background import BackgroundScheduler


db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Start scheduler for escalation checks
    scheduler = BackgroundScheduler(daemon=True)

    def job_wrapper():
        with app.app_context():
            check_overdue_checkpoints()

    scheduler.add_job(job_wrapper, 'interval', minutes=1, id='overdue_checkpoints', replace_existing=True)
    scheduler.start()

    register_routes(app)
    return app


# Models
class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(TimestampMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(256))
    role = db.Column(db.String(128), index=True)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Workflow(TimestampMixin, db.Model):
    __tablename__ = 'workflows'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)

    tasks = db.relationship('Task', backref='workflow', lazy=True)
    rules = db.relationship('EscalationRule', backref='workflow', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
        }


class Task(TimestampMixin, db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflows.id'), nullable=False)
    status = db.Column(db.String(32), default='new', index=True)  # new, in_review, approved, rejected
    payload = db.Column(db.JSON, default={})

    checkpoints = db.relationship('Checkpoint', backref='task', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow.name if self.workflow else None,
            'status': self.status,
            'payload': self.payload,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Checkpoint(TimestampMixin, db.Model):
    __tablename__ = 'checkpoints'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    name = db.Column(db.String(256), nullable=False)

    status = db.Column(db.String(32), default='pending', index=True)  # pending, approved, rejected

    assigned_role = db.Column(db.String(128), index=True)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    level = db.Column(db.Integer, default=0)  # escalation level index within the chain
    escalation_chain = db.Column(db.JSON, default=[])  # list of roles or user names

    sla_minutes = db.Column(db.Integer, default=60)
    due_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    last_notified_at = db.Column(db.DateTime, nullable=True)

    assigned_user = db.relationship('User', foreign_keys=[assigned_user_id])

    def assigned_to_label(self) -> str:
        if self.assigned_user:
            return f'user:{self.assigned_user.name}'
        return f'role:{self.assigned_role}' if self.assigned_role else 'unassigned'

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'name': self.name,
            'status': self.status,
            'assigned_role': self.assigned_role,
            'assigned_user_id': self.assigned_user_id,
            'assigned_to': self.assigned_to_label(),
            'level': self.level,
            'escalation_chain': self.escalation_chain,
            'sla_minutes': self.sla_minutes,
            'due_at': self.due_at.isoformat() if self.due_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'last_notified_at': self.last_notified_at.isoformat() if self.last_notified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EscalationRule(TimestampMixin, db.Model):
    __tablename__ = 'escalation_rules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflows.id'), nullable=True)
    priority = db.Column(db.Integer, default=100, index=True)

    condition = db.Column(db.JSON, default={})  # condition DSL
    gate_name = db.Column(db.String(256), nullable=True)

    assign_role = db.Column(db.String(128), nullable=True)
    sla_minutes = db.Column(db.Integer, default=60)
    escalation_chain = db.Column(db.JSON, default=[])  # list of roles (strings)

    auto_approve = db.Column(db.Boolean, default=False)

    @validates('escalation_chain')
    def validate_chain(self, key, chain):
        if chain is None:
            return []
        if not isinstance(chain, list):
            raise ValueError('escalation_chain must be a list of role strings')
        return chain

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow.name if self.workflow else None,
            'priority': self.priority,
            'condition': self.condition,
            'gate_name': self.gate_name,
            'assign_role': self.assign_role,
            'sla_minutes': self.sla_minutes,
            'escalation_chain': self.escalation_chain,
            'auto_approve': self.auto_approve,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(TimestampMixin, db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(64))
    entity_id = db.Column(db.Integer)
    action = db.Column(db.String(128))
    data = db.Column(db.JSON, default={})

    def to_dict(self):
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'data': self.data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# Utility functions

def get_current_user() -> Optional[User]:
    username = request.headers.get('X-User') or request.args.get('user')
    if not username:
        return None
    return User.query.filter_by(name=username).first()


def ensure_user() -> User:
    user = get_current_user()
    if not user:
        abort(401, description='User not identified. Provide X-User header or ?user= param.')
    return user


def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    parts = path.split('.')
    cur = data
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def check_clause(clause: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    op = clause.get('op') or clause.get('operator')
    field = clause.get('field')
    value = clause.get('value')

    if op == 'always':
        return True
    if op == 'exists':
        return get_nested_value(payload, field) is not None
    if op == 'not_exists':
        return get_nested_value(payload, field) is None

    left = get_nested_value(payload, field)

    if op in ('==', 'eq'):
        return left == value
    if op in ('!=', 'ne'):
        return left != value
    if op == '>':
        try:
            return left > value
        except Exception:
            return False
    if op == '>=':
        try:
            return left >= value
        except Exception:
            return False
    if op == '<':
        try:
            return left < value
        except Exception:
            return False
    if op == '<=':
        try:
            return left <= value
        except Exception:
            return False
    if op == 'in':
        try:
            return left in value
        except Exception:
            return False
    if op == 'not_in':
        try:
            return left not in value
        except Exception:
            return False
    if op == 'contains':
        try:
            return value in left
        except Exception:
            return False
    return False


def match_condition(condition: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    if not condition:
        return True
    if 'all' in condition:
        return all(check_clause(c, payload) for c in condition['all'])
    if 'any' in condition:
        return any(check_clause(c, payload) for c in condition['any'])
    # single-clause
    return check_clause(condition, payload)


def send_notification(msg: str, role: Optional[str] = None, user: Optional[User] = None):
    target = f'user:{user.name}' if user else f'role:{role}' if role else 'broadcast'
    print(f"[NOTIFY] to {target}: {msg}")


def log_action(entity_type: str, entity_id: int, action: str, data: Dict[str, Any]):
    entry = AuditLog(entity_type=entity_type, entity_id=entity_id, action=action, data=data)
    db.session.add(entry)


def create_checkpoints_for_task(task: Task):
    rules = EscalationRule.query.filter(
        (EscalationRule.workflow_id == task.workflow_id) | (EscalationRule.workflow_id.is_(None))
    ).order_by(EscalationRule.priority.asc()).all()

    created_any = False

    for rule in rules:
        if match_condition(rule.condition, task.payload):
            if rule.auto_approve:
                log_action('task', task.id, 'auto_approved_by_rule', {'rule_id': rule.id, 'rule_name': rule.name})
                continue
            cp = Checkpoint(
                task_id=task.id,
                name=rule.gate_name or f"Gate: {rule.name}",
                status='pending',
                assigned_role=rule.assign_role,
                sla_minutes=rule.sla_minutes or 60,
                escalation_chain=rule.escalation_chain or ([rule.assign_role] if rule.assign_role else []),
                level=0,
                due_at=datetime.utcnow() + timedelta(minutes=(rule.sla_minutes or 60)),
            )
            db.session.add(cp)
            db.session.flush()
            log_action('checkpoint', cp.id, 'created', {
                'rule_id': rule.id,
                'rule_name': rule.name,
                'assigned_role': cp.assigned_role,
                'sla_minutes': cp.sla_minutes,
                'escalation_chain': cp.escalation_chain,
            })
            created_any = True
            if cp.assigned_role:
                send_notification(f"New checkpoint '{cp.name}' for Task #{task.id}", role=cp.assigned_role)

    if created_any:
        task.status = 'in_review'
    else:
        task.status = 'approved'
        log_action('task', task.id, 'approved_no_gates', {})


def check_overdue_checkpoints():
    now = datetime.utcnow()
    overdue = Checkpoint.query.filter(
        Checkpoint.status == 'pending',
        Checkpoint.due_at.isnot(None),
        Checkpoint.due_at <= now,
    ).all()

    for cp in overdue:
        chain = cp.escalation_chain or []
        if chain and cp.level < (len(chain) - 1):
            # escalate to next role in chain
            cp.level += 1
            cp.assigned_role = chain[cp.level]
            cp.due_at = now + timedelta(minutes=cp.sla_minutes or 60)
            cp.last_notified_at = now
            log_action('checkpoint', cp.id, 'escalated', {
                'new_level': cp.level,
                'assigned_role': cp.assigned_role,
            })
            send_notification(f"Escalation to level {cp.level} for checkpoint '{cp.name}' (Task #{cp.task_id})", role=cp.assigned_role)
        else:
            # last level: send reminder and extend
            cp.due_at = now + timedelta(minutes=cp.sla_minutes or 60)
            cp.last_notified_at = now
            log_action('checkpoint', cp.id, 'reminder_sent', {
                'level': cp.level,
                'assigned_role': cp.assigned_role,
            })
            if cp.assigned_user:
                send_notification(f"Reminder: checkpoint '{cp.name}' (Task #{cp.task_id}) overdue", user=cp.assigned_user)
            else:
                send_notification(f"Reminder: checkpoint '{cp.name}' (Task #{cp.task_id}) overdue", role=cp.assigned_role)

    if overdue:
        db.session.commit()


def seed_users():
    users = [
        {'name': 'alice', 'email': 'alice@example.com', 'role': 'finance_analyst'},
        {'name': 'bob', 'email': 'bob@example.com', 'role': 'finance_manager'},
        {'name': 'carol', 'email': 'carol@example.com', 'role': 'cfo'},
        {'name': 'dave', 'email': 'dave@example.com', 'role': 'compliance'},
        {'name': 'eve', 'email': 'eve@example.com', 'role': 'ops'},
    ]
    created = []
    for u in users:
        if not User.query.filter_by(name=u['name']).first():
            user = User(name=u['name'], email=u['email'], role=u['role'])
            db.session.add(user)
            created.append(user.name)
    if created:
        db.session.commit()
    return created


def seed_workflow_and_rules():
    wf = Workflow.query.filter_by(name='Expense Report').first()
    if not wf:
        wf = Workflow(name='Expense Report', description='Expense approval workflow with human-in-the-loop gates')
        db.session.add(wf)
        db.session.commit()

    created = []
    # Rule 1: Expenses >= 5000 require Finance chain
    if not EscalationRule.query.filter_by(name='Finance Review >= 5000').first():
        r1 = EscalationRule(
            name='Finance Review >= 5000',
            workflow_id=wf.id,
            priority=10,
            condition={'all': [ {'field': 'amount', 'op': '>=', 'value': 5000} ]},
            gate_name='Finance Review',
            assign_role='finance_analyst',
            sla_minutes=60,
            escalation_chain=['finance_analyst', 'finance_manager', 'cfo'],
            auto_approve=False,
        )
        db.session.add(r1)
        created.append(r1.name)

    # Rule 2: Expenses >= 20000 also require Compliance
    if not EscalationRule.query.filter_by(name='Compliance Review >= 20000').first():
        r2 = EscalationRule(
            name='Compliance Review >= 20000',
            workflow_id=wf.id,
            priority=5,
            condition={'all': [ {'field': 'amount', 'op': '>=', 'value': 20000} ]},
            gate_name='Compliance Review',
            assign_role='compliance',
            sla_minutes=120,
            escalation_chain=['compliance', 'cfo'],
            auto_approve=False,
        )
        db.session.add(r2)
        created.append(r2.name)

    # Rule 3: Low amount auto-approve
    if not EscalationRule.query.filter_by(name='Auto-approve < 100').first():
        r3 = EscalationRule(
            name='Auto-approve < 100',
            workflow_id=wf.id,
            priority=1,
            condition={'all': [ {'field': 'amount', 'op': '<', 'value': 100} ]},
            gate_name='Auto-Approve Gate',
            assign_role=None,
            sla_minutes=0,
            escalation_chain=[],
            auto_approve=True,
        )
        db.session.add(r3)
        created.append(r3.name)

    db.session.commit()
    return wf, created


# Routes

def register_routes(app: Flask):
    @app.route('/')
    def index():
        user = get_current_user()
        return render_template('index.html', user=user)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'time': datetime.utcnow().isoformat()})

    @app.route('/whoami')
    def whoami():
        user = get_current_user()
        if not user:
            return jsonify({'user': None}), 200
        return jsonify({'user': user.to_dict()})

    @app.route('/init', methods=['POST', 'GET'])
    def init():
        db.create_all()
        users_created = seed_users()
        wf, rules_created = seed_workflow_and_rules()
        return jsonify({'ok': True, 'users_created': users_created, 'workflow': wf.to_dict(), 'rules_created': rules_created})

    # Rules
    @app.route('/rules', methods=['GET', 'POST'])
    def rules():
        if request.method == 'POST':
            data = request.get_json(force=True)
            wf_name = data.get('workflow_name')
            wf = None
            if wf_name:
                wf = Workflow.query.filter_by(name=wf_name).first()
                if not wf:
                    wf = Workflow(name=wf_name)
                    db.session.add(wf)
                    db.session.commit()
            rule = EscalationRule(
                name=data['name'],
                workflow_id=wf.id if wf else None,
                priority=data.get('priority', 100),
                condition=data.get('condition', {}),
                gate_name=data.get('gate_name'),
                assign_role=data.get('assign_role'),
                sla_minutes=data.get('sla_minutes', 60),
                escalation_chain=data.get('escalation_chain', []),
                auto_approve=data.get('auto_approve', False),
            )
            db.session.add(rule)
            db.session.commit()
            return jsonify({'ok': True, 'rule': rule.to_dict()})
        # GET
        if request.args.get('json'):
            return jsonify([r.to_dict() for r in EscalationRule.query.order_by(EscalationRule.priority.asc()).all()])
        return render_template('rules.html', rules=EscalationRule.query.order_by(EscalationRule.priority.asc()).all())

    # Tasks
    @app.route('/tasks', methods=['GET', 'POST'])
    def tasks():
        if request.method == 'POST':
            data = request.get_json(force=True)
            wf_name = data.get('workflow_name') or 'Expense Report'
            wf = Workflow.query.filter_by(name=wf_name).first()
            if not wf:
                abort(400, description='Workflow not found')
            t = Task(workflow_id=wf.id, payload=data.get('payload', {}), status='new')
            db.session.add(t)
            db.session.flush()
            create_checkpoints_for_task(t)
            db.session.commit()
            return jsonify({'ok': True, 'task': t.to_dict()})
        # GET
        q = Task.query.order_by(Task.created_at.desc()).all()
        if request.args.get('json'):
            return jsonify([t.to_dict() for t in q])
        return render_template('tasks.html', tasks=q)

    @app.route('/tasks/<int:task_id>', methods=['GET'])
    def task_detail(task_id):
        t = Task.query.get_or_404(task_id)
        if request.args.get('json'):
            data = t.to_dict()
            data['checkpoints'] = [c.to_dict() for c in t.checkpoints]
            return jsonify(data)
        return render_template('task_detail.html', task=t)

    @app.route('/checkpoints/<int:cp_id>/approve', methods=['POST'])
    def approve_checkpoint(cp_id):
        user = ensure_user()
        cp = Checkpoint.query.get_or_404(cp_id)
        if not is_user_authorized_for_checkpoint(user, cp):
            abort(403, description='Not authorized to approve this checkpoint')
        if cp.status != 'pending':
            abort(400, description='Checkpoint is not pending')
        cp.status = 'approved'
        cp.resolved_at = datetime.utcnow()
        db.session.add(cp)
        log_action('checkpoint', cp.id, 'approved', {'by': user.name})
        update_task_status_from_checkpoints(cp.task)
        db.session.commit()
        return redirect_after_action(cp)

    @app.route('/checkpoints/<int:cp_id>/reject', methods=['POST'])
    def reject_checkpoint(cp_id):
        user = ensure_user()
        cp = Checkpoint.query.get_or_404(cp_id)
        if not is_user_authorized_for_checkpoint(user, cp):
            abort(403, description='Not authorized to reject this checkpoint')
        if cp.status != 'pending':
            abort(400, description='Checkpoint is not pending')
        cp.status = 'rejected'
        cp.resolved_at = datetime.utcnow()
        db.session.add(cp)
        log_action('checkpoint', cp.id, 'rejected', {'by': user.name})
        cp.task.status = 'rejected'
        log_action('task', cp.task.id, 'rejected_due_to_checkpoint', {'checkpoint_id': cp.id})
        db.session.commit()
        return redirect_after_action(cp)

    def redirect_after_action(cp: Checkpoint):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'ok': True, 'checkpoint': cp.to_dict(), 'task': cp.task.to_dict()})
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        # Default: go back to inbox for current user
        user = get_current_user()
        if user:
            return redirect(url_for('inbox') + f'?user={user.name}')
        return redirect(url_for('task_detail', task_id=cp.task_id))

    @app.route('/inbox', methods=['GET'])
    def inbox():
        user = ensure_user()
        cps = Checkpoint.query.filter(
            Checkpoint.status == 'pending',
            ((Checkpoint.assigned_user_id == user.id) | (Checkpoint.assigned_user_id.is_(None))),
        ).filter(
            (Checkpoint.assigned_role == user.role) | (Checkpoint.assigned_user_id == user.id)
        ).order_by(Checkpoint.due_at.asc().nullsfirst(), Checkpoint.created_at.asc()).all()

        if request.args.get('json'):
            return jsonify({'user': user.to_dict(), 'checkpoints': [c.to_dict() for c in cps]})
        return render_template('inbox.html', user=user, checkpoints=cps)

    @app.route('/assign/<int:cp_id>', methods=['POST'])
    def assign_checkpoint(cp_id):
        # Optional endpoint to self-assign a checkpoint if allowed by role
        user = ensure_user()
        cp = Checkpoint.query.get_or_404(cp_id)
        if cp.status != 'pending':
            abort(400, description='Checkpoint not pending')
        if cp.assigned_user_id:
            abort(400, description='Already assigned')
        if cp.assigned_role and cp.assigned_role != user.role:
            abort(403, description='Role mismatch for assignment')
        cp.assigned_user_id = user.id
        cp.last_notified_at = datetime.utcnow()
        db.session.add(cp)
        log_action('checkpoint', cp.id, 'assigned', {'assigned_user': user.name})
        db.session.commit()
        return redirect(url_for('inbox') + f'?user={user.name}')

    @app.route('/audit', methods=['GET'])
    def audit():
        entries = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
        return jsonify([e.to_dict() for e in entries])


def is_user_authorized_for_checkpoint(user: User, cp: Checkpoint) -> bool:
    if cp.assigned_user_id:
        return cp.assigned_user_id == user.id
    if cp.assigned_role:
        return user.role == cp.assigned_role
    # Unassigned checkpoint can be actioned by role match
    return True


def update_task_status_from_checkpoints(task: Task):
    statuses = [cp.status for cp in task.checkpoints]
    if any(s == 'rejected' for s in statuses):
        task.status = 'rejected'
        return
    if all(s == 'approved' for s in statuses) and statuses:
        task.status = 'approved'
        log_action('task', task.id, 'approved_all_gates', {})
    else:
        task.status = 'in_review'


app = create_app()


if __name__ == '__main__':
    # Run using: python app.py
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)



@app.route('/escalation', methods=['POST'])
def _auto_stub_escalation():
    return 'Auto-generated stub for /escalation', 200
