import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# Configuration
DB_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Role constants
ROLES = {"owner", "reviewer", "dev", "viewer"}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    memberships = db.relationship("Membership", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    memberships = db.relationship("Membership", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self, include_members=False):
        data = {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
        }
        if include_members:
            data["members"] = [m.to_dict(include_user=True) for m in self.memberships]
        else:
            data["member_count"] = len(self.memberships)
        return data


class Membership(db.Model):
    __tablename__ = "memberships"
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    role = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="memberships")
    project = db.relationship("Project", back_populates="memberships")

    def to_dict(self, include_user=False, include_project=False):
        data = {
            "project_id": self.project_id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }
        if include_user:
            data["user"] = self.user.to_dict() if self.user else None
        if include_project:
            data["project"] = self.project.to_dict(include_members=False) if self.project else None
        return data


# Database initialization
with app.app_context():
    db.create_all()


# Helpers

def error_response(status, message, details=None):
    payload = {"error": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def get_actor():
    actor_id = request.headers.get("X-Actor-Id")
    if not actor_id:
        return None, (401, "Missing X-Actor-Id header")
    try:
        actor_id_int = int(actor_id)
    except ValueError:
        return None, (400, "Invalid X-Actor-Id header; must be integer")
    actor = db.session.get(User, actor_id_int)
    if not actor:
        return None, (404, f"Actor user {actor_id_int} not found")
    return actor, None


def normalize_role(role_str):
    if not isinstance(role_str, str):
        return None
    r = role_str.strip().lower()
    return r if r in ROLES else None


def require_project(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return None, (404, f"Project {project_id} not found")
    return project, None


def is_owner(project_id, user_id):
    return (
        db.session.query(Membership)
        .filter_by(project_id=project_id, user_id=user_id, role="owner")
        .first()
        is not None
    )


def require_owner(project_id, actor_id):
    if not is_owner(project_id, actor_id):
        return (403, "Actor must be an owner of the project to perform this action")
    return None


def owner_count(project_id):
    return (
        db.session.query(Membership)
        .filter_by(project_id=project_id, role="owner")
        .count()
    )


# Routes

@app.errorhandler(404)
def not_found(_e):
    return error_response(404, "Not found")


@app.errorhandler(405)
def method_not_allowed(_e):
    return error_response(405, "Method not allowed")


@app.errorhandler(500)
def internal_error(_e):
    return error_response(500, "Internal server error")


# Users
@app.post("/users")
def create_user():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    if not name:
        return error_response(400, "Field 'name' is required")
    if not email:
        return error_response(400, "Field 'email' is required")
    if db.session.query(User).filter_by(email=email).first():
        return error_response(409, "Email already exists")
    user = User(name=name, email=email)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@app.get("/users")
def list_users():
    users = db.session.query(User).order_by(User.id.asc()).all()
    return jsonify([u.to_dict() for u in users])


@app.get("/users/<int:user_id>")
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, f"User {user_id} not found")
    return jsonify(user.to_dict())


@app.get("/users/<int:user_id>/projects")
def list_user_projects(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, f"User {user_id} not found")
    memberships = (
        db.session.query(Membership)
        .filter_by(user_id=user_id)
        .join(Project, Membership.project_id == Project.id)
        .order_by(Project.id.asc())
        .all()
    )
    return jsonify([
        {
            "project": db.session.get(Project, m.project_id).to_dict(include_members=False),
            "role": m.role,
        }
        for m in memberships
    ])


# Projects
@app.post("/projects")
def create_project():
    actor, err = get_actor()
    if err:
        return error_response(*err)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return error_response(400, "Field 'name' is required")
    if db.session.query(Project).filter_by(name=name).first():
        return error_response(409, "Project name already exists")
    project = Project(name=name)
    db.session.add(project)
    db.session.flush()
    # Creator becomes owner
    membership = Membership(project_id=project.id, user_id=actor.id, role="owner")
    db.session.add(membership)
    db.session.commit()
    return jsonify(project.to_dict(include_members=True)), 201


@app.get("/projects")
def list_projects():
    projects = db.session.query(Project).order_by(Project.id.asc()).all()
    return jsonify([p.to_dict(include_members=False) for p in projects])


@app.get("/projects/<int:project_id>")
def get_project(project_id):
    project, err = require_project(project_id)
    if err:
        return error_response(*err)
    return jsonify(project.to_dict(include_members=True))


@app.get("/projects/<int:project_id>/members")
def list_project_members(project_id):
    project, err = require_project(project_id)
    if err:
        return error_response(*err)
    memberships = (
        db.session.query(Membership)
        .filter_by(project_id=project_id)
        .join(User, Membership.user_id == User.id)
        .order_by(Membership.role.desc(), User.id.asc())
        .all()
    )
    return jsonify([m.to_dict(include_user=True) for m in memberships])


@app.post("/projects/<int:project_id>/access/grant")
def grant_access(project_id):
    actor, err = get_actor()
    if err:
        return error_response(*err)
    project, errp = require_project(project_id)
    if errp:
        return error_response(*errp)
    perm_err = require_owner(project_id, actor.id)
    if perm_err:
        return error_response(*perm_err)

    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
    except Exception:
        return error_response(400, "Field 'user_id' is required and must be integer")
    role = normalize_role(data.get("role"))
    if not role:
        return error_response(400, f"Field 'role' is required and must be one of {sorted(list(ROLES))}")

    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, f"User {user_id} not found")

    existing = db.session.query(Membership).filter_by(project_id=project_id, user_id=user_id).first()
    if existing:
        return error_response(409, "User already has access to this project")

    membership = Membership(project_id=project_id, user_id=user_id, role=role)
    db.session.add(membership)
    db.session.commit()
    return jsonify({
        "message": "Access granted",
        "membership": membership.to_dict(include_user=True, include_project=True),
    }), 201


@app.post("/projects/<int:project_id>/access/revoke")
def revoke_access(project_id):
    actor, err = get_actor()
    if err:
        return error_response(*err)
    project, errp = require_project(project_id)
    if errp:
        return error_response(*errp)
    perm_err = require_owner(project_id, actor.id)
    if perm_err:
        return error_response(*perm_err)

    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
    except Exception:
        return error_response(400, "Field 'user_id' is required and must be integer")

    membership = db.session.query(Membership).filter_by(project_id=project_id, user_id=user_id).first()
    if not membership:
        return error_response(404, "Membership not found")

    # Prevent removing the last owner
    if membership.role == "owner" and owner_count(project_id) <= 1:
        return error_response(409, "Cannot revoke access: project must have at least one owner")

    db.session.delete(membership)
    db.session.commit()
    return jsonify({"message": "Access revoked", "project_id": project_id, "user_id": user_id})


@app.put("/projects/<int:project_id>/access/update")
def update_access(project_id):
    actor, err = get_actor()
    if err:
        return error_response(*err)
    project, errp = require_project(project_id)
    if errp:
        return error_response(*errp)
    perm_err = require_owner(project_id, actor.id)
    if perm_err:
        return error_response(*perm_err)

    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
    except Exception:
        return error_response(400, "Field 'user_id' is required and must be integer")
    new_role = normalize_role(data.get("role"))
    if not new_role:
        return error_response(400, f"Field 'role' is required and must be one of {sorted(list(ROLES))}")

    membership = db.session.query(Membership).filter_by(project_id=project_id, user_id=user_id).first()
    if not membership:
        return error_response(404, "Membership not found")

    # If demoting an owner, ensure not the last one
    if membership.role == "owner" and new_role != "owner" and owner_count(project_id) <= 1:
        return error_response(409, "Cannot change role: project must have at least one owner")

    membership.role = new_role
    db.session.commit()
    return jsonify({
        "message": "Access updated",
        "membership": membership.to_dict(include_user=True, include_project=True),
    })


# Health endpoint
@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app
