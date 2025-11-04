import csv
import os
from datetime import datetime
from extensions import db
from models import Team, Project, ResourceUsage
from sqlalchemy import func


def ensure_reports_dir(path):
    os.makedirs(path, exist_ok=True)


def _dt(dt):
    return dt.strftime('%Y-%m-%d')


def generate_team_report(start_dt, end_dt, reports_dir):
    ensure_reports_dir(reports_dir)
    filename = f"team-usage_{_dt(start_dt)}_to_{_dt(end_dt)}.csv"
    filepath = os.path.join(reports_dir, filename)

    q = (
        db.session.query(
            Team.name.label('team'),
            func.sum(ResourceUsage.cpu_hours).label('cpu_hours'),
            func.sum(ResourceUsage.memory_gb_hours).label('memory_gb_hours'),
            func.sum(ResourceUsage.storage_gb).label('storage_gb'),
            func.sum(ResourceUsage.cost).label('cost'),
        )
        .join(Project, Project.team_id == Team.id)
        .join(ResourceUsage, ResourceUsage.project_id == Project.id)
        .filter(ResourceUsage.timestamp >= start_dt, ResourceUsage.timestamp < end_dt)
        .group_by(Team.name)
        .order_by(Team.name)
    )

    with open(filepath, 'w', newline='') as fp:
        writer = csv.writer(fp)
        writer.writerow(['Team', 'CPU Hours', 'Memory GB Hours', 'Storage GB', 'Cost'])
        for r in q.all():
            writer.writerow([
                r.team,
                float(r.cpu_hours or 0),
                float(r.memory_gb_hours or 0),
                float(r.storage_gb or 0),
                float(r.cost or 0),
            ])
    return filepath


def generate_project_report(start_dt, end_dt, reports_dir):
    ensure_reports_dir(reports_dir)
    filename = f"project-usage_{_dt(start_dt)}_to_{_dt(end_dt)}.csv"
    filepath = os.path.join(reports_dir, filename)

    q = (
        db.session.query(
            Team.name.label('team'),
            Project.name.label('project'),
            func.sum(ResourceUsage.cpu_hours).label('cpu_hours'),
            func.sum(ResourceUsage.memory_gb_hours).label('memory_gb_hours'),
            func.sum(ResourceUsage.storage_gb).label('storage_gb'),
            func.sum(ResourceUsage.cost).label('cost'),
        )
        .join(Project, ResourceUsage.project_id == Project.id)
        .join(Team, Project.team_id == Team.id)
        .filter(ResourceUsage.timestamp >= start_dt, ResourceUsage.timestamp < end_dt)
        .group_by(Team.name, Project.name)
        .order_by(Team.name, Project.name)
    )

    with open(filepath, 'w', newline='') as fp:
        writer = csv.writer(fp)
        writer.writerow(['Team', 'Project', 'CPU Hours', 'Memory GB Hours', 'Storage GB', 'Cost'])
        for r in q.all():
            writer.writerow([
                r.team,
                r.project,
                float(r.cpu_hours or 0),
                float(r.memory_gb_hours or 0),
                float(r.storage_gb or 0),
                float(r.cost or 0),
            ])
    return filepath


def list_reports(reports_dir):
    ensure_reports_dir(reports_dir)
    files = []
    for fname in os.listdir(reports_dir):
        if fname.endswith('.csv'):
            path = os.path.join(reports_dir, fname)
            files.append({
                'filename': fname,
                'size_bytes': os.path.getsize(path),
                'modified': datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
            })
    files.sort(key=lambda x: x['filename'])
    return files

