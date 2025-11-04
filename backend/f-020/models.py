from datetime import datetime
from sqlalchemy import func
from extensions import db

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    projects = db.relationship('Project', backref='team', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team {self.name}>"

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    usage = db.relationship('ResourceUsage', backref='project', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name} (Team {self.team_id})>"

class ResourceUsage(db.Model):
    __tablename__ = 'resource_usage'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cpu_hours = db.Column(db.Float, nullable=False, default=0.0)
    memory_gb_hours = db.Column(db.Float, nullable=False, default=0.0)
    storage_gb = db.Column(db.Float, nullable=False, default=0.0)
    cost = db.Column(db.Float, nullable=False, default=0.0)

    def __repr__(self):
        return f"<Usage P{self.project_id} @ {self.timestamp}>"

# Helper aggregations

def aggregate_usage_by_team(start_dt, end_dt):
    from sqlalchemy.orm import aliased
    q = (
        db.session.query(
            Team.id.label('team_id'),
            Team.name.label('team_name'),
            func.sum(ResourceUsage.cpu_hours).label('cpu_hours'),
            func.sum(ResourceUsage.memory_gb_hours).label('memory_gb_hours'),
            func.sum(ResourceUsage.storage_gb).label('storage_gb'),
            func.sum(ResourceUsage.cost).label('cost'),
        )
        .join(Project, Project.team_id == Team.id)
        .join(ResourceUsage, ResourceUsage.project_id == Project.id)
        .filter(ResourceUsage.timestamp >= start_dt, ResourceUsage.timestamp < end_dt)
        .group_by(Team.id, Team.name)
        .order_by(Team.name.asc())
    )
    return [
        {
            'team_id': r.team_id,
            'team_name': r.team_name,
            'cpu_hours': float(r.cpu_hours or 0),
            'memory_gb_hours': float(r.memory_gb_hours or 0),
            'storage_gb': float(r.storage_gb or 0),
            'cost': float(r.cost or 0),
        }
        for r in q.all()
    ]


def aggregate_usage_by_project_for_team(team_id, start_dt, end_dt):
    q = (
        db.session.query(
            Project.id.label('project_id'),
            Project.name.label('project_name'),
            func.sum(ResourceUsage.cpu_hours).label('cpu_hours'),
            func.sum(ResourceUsage.memory_gb_hours).label('memory_gb_hours'),
            func.sum(ResourceUsage.storage_gb).label('storage_gb'),
            func.sum(ResourceUsage.cost).label('cost'),
        )
        .join(ResourceUsage, ResourceUsage.project_id == Project.id)
        .filter(Project.team_id == team_id)
        .filter(ResourceUsage.timestamp >= start_dt, ResourceUsage.timestamp < end_dt)
        .group_by(Project.id, Project.name)
        .order_by(Project.name.asc())
    )
    return [
        {
            'project_id': r.project_id,
            'project_name': r.project_name,
            'cpu_hours': float(r.cpu_hours or 0),
            'memory_gb_hours': float(r.memory_gb_hours or 0),
            'storage_gb': float(r.storage_gb or 0),
            'cost': float(r.cost or 0),
        }
        for r in q.all()
    ]


def timeseries_usage_for_project(project_id, start_dt, end_dt, group='day'):
    if group == 'week':
        date_expr = func.strftime('%Y-%W', ResourceUsage.timestamp)
    else:
        date_expr = func.strftime('%Y-%m-%d', ResourceUsage.timestamp)

    q = (
        db.session.query(
            date_expr.label('bucket'),
            func.sum(ResourceUsage.cpu_hours).label('cpu_hours'),
            func.sum(ResourceUsage.memory_gb_hours).label('memory_gb_hours'),
            func.sum(ResourceUsage.storage_gb).label('storage_gb'),
            func.sum(ResourceUsage.cost).label('cost'),
        )
        .filter(ResourceUsage.project_id == project_id)
        .filter(ResourceUsage.timestamp >= start_dt, ResourceUsage.timestamp < end_dt)
        .group_by('bucket')
        .order_by('bucket')
    )
    return [
        {
            'bucket': r.bucket,
            'cpu_hours': float(r.cpu_hours or 0),
            'memory_gb_hours': float(r.memory_gb_hours or 0),
            'storage_gb': float(r.storage_gb or 0),
            'cost': float(r.cost or 0),
        }
        for r in q.all()
    ]


def timeseries_usage_for_team(team_id, start_dt, end_dt, group='day'):
    if group == 'week':
        date_expr = func.strftime('%Y-%W', ResourceUsage.timestamp)
    else:
        date_expr = func.strftime('%Y-%m-%d', ResourceUsage.timestamp)

    q = (
        db.session.query(
            date_expr.label('bucket'),
            func.sum(ResourceUsage.cpu_hours).label('cpu_hours'),
            func.sum(ResourceUsage.memory_gb_hours).label('memory_gb_hours'),
            func.sum(ResourceUsage.storage_gb).label('storage_gb'),
            func.sum(ResourceUsage.cost).label('cost'),
        )
        .join(Project, ResourceUsage.project_id == Project.id)
        .filter(Project.team_id == team_id)
        .filter(ResourceUsage.timestamp >= start_dt, ResourceUsage.timestamp < end_dt)
        .group_by('bucket')
        .order_by('bucket')
    )
    return [
        {
            'bucket': r.bucket,
            'cpu_hours': float(r.cpu_hours or 0),
            'memory_gb_hours': float(r.memory_gb_hours or 0),
            'storage_gb': float(r.storage_gb or 0),
            'cost': float(r.cost or 0),
        }
        for r in q.all()
    ]

