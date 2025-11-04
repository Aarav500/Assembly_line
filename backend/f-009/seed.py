import os
import random
from datetime import datetime, timedelta, date

from app import db, Deployment, Incident, app

SERVICES = ['payments', 'orders', 'users']
ENVS = ['prod', 'staging']

random.seed(42)


def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        today = date.today()
        start = today - timedelta(days=89)

        deployments = []
        incidents = []

        for d in range(90):
            the_date = start + timedelta(days=d)
            for service in SERVICES:
                for env in ENVS:
                    # between 0 and 5 deployments per day per service/env
                    deploy_count = random.randint(0, 5)
                    for _ in range(deploy_count):
                        hour = random.randint(8, 22)
                        minute = random.randint(0, 59)
                        deployed_at = datetime(the_date.year, the_date.month, the_date.day, hour, minute)
                        lead_time = random.randint(600, 48 * 3600)  # 10 minutes to 48h
                        failed = random.random() < 0.1  # 10% fail rate baseline
                        dep = Deployment(service=service, environment=env, deployed_at=deployed_at,
                                         lead_time_seconds=lead_time, failed=failed,
                                         notes=None)
                        deployments.append(dep)

                        # occasionally create incident linked to failed deployment
                        if failed and random.random() < 0.6:
                            start_offset_min = random.randint(0, 120)
                            mttr = random.randint(5 * 60, 6 * 3600)  # 5 min to 6h
                            started_at = deployed_at + timedelta(minutes=start_offset_min)
                            restored_at = started_at + timedelta(seconds=mttr)
                            inc = Incident(deployment=dep, service=service, environment=env,
                                           started_at=started_at, restored_at=restored_at,
                                           notes='Auto-generated in seed')
                            incidents.append(inc)

                    # non-deployment incidents (e.g., infra issues)
                    if random.random() < 0.03:
                        hour = random.randint(0, 23)
                        minute = random.randint(0, 59)
                        started_at = datetime(the_date.year, the_date.month, the_date.day, hour, minute)
                        mttr = random.randint(10 * 60, 12 * 3600)
                        restored_at = started_at + timedelta(seconds=mttr)
                        inc = Incident(deployment=None, service=service, environment=env,
                                       started_at=started_at, restored_at=restored_at,
                                       notes='Infra-related incident')
                        incidents.append(inc)

        db.session.add_all(deployments)
        db.session.commit()
        db.session.add_all(incidents)
        db.session.commit()
        print(f'Seeded {len(deployments)} deployments, {len(incidents)} incidents')


if __name__ == '__main__':
    seed()

