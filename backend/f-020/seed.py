import random
from datetime import datetime, timedelta
from app import create_app
from extensions import db
from models import Team, Project, ResourceUsage


def seed():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        team_names = ["Alpha", "Beta", "Gamma"]
        projects_by_team = {
            "Alpha": ["API", "Web"],
            "Beta": ["Data", "ML"],
            "Gamma": ["Infra", "Ops"],
        }

        teams = {}
        for t in team_names:
            team = Team(name=t)
            db.session.add(team)
            teams[t] = team
        db.session.commit()

        projects = {}
        for t, pnames in projects_by_team.items():
            for pname in pnames:
                p = Project(name=pname, team_id=teams[t].id)
                db.session.add(p)
                projects[pname] = p
        db.session.commit()

        # Generate 90 days of daily usage per project
        end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=90)
        current = start
        entries = []
        random.seed(42)
        while current < end:
            for p in projects.values():
                cpu = max(0, random.gauss(50, 15))
                mem = max(0, random.gauss(120, 40))
                storage = max(0, random.gauss(500, 120))
                cost = round(cpu * 0.05 + mem * 0.01 + storage * 0.002, 2)
                entries.append(ResourceUsage(
                    project_id=p.id,
                    timestamp=current + timedelta(hours=12),
                    cpu_hours=round(cpu, 2),
                    memory_gb_hours=round(mem, 2),
                    storage_gb=round(storage, 2),
                    cost=cost,
                ))
            current += timedelta(days=1)
        db.session.bulk_save_objects(entries)
        db.session.commit()
        print(f"Seeded {len(entries)} usage rows across {len(projects)} projects and {len(teams)} teams")


if __name__ == "__main__":
    seed()

