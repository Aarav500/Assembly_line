from app import app, db
from models import Tenant, Project, Resource
from utils.tags import upsert_tags


with app.app_context():
    # Clear existing for demo purposes only
    # db.drop_all(); db.create_all()

    if not Tenant.query.filter_by(name='Acme Corp').first():
        t = Tenant(name='Acme Corp')
        db.session.add(t)
        db.session.flush()

        p1 = Project(name='website', tenant_id=t.id)
        p2 = Project(name='data-platform', tenant_id=t.id)
        db.session.add_all([p1, p2])
        db.session.flush()

        r1 = Resource(name='web-frontend-1', type='vm', size='small', base_rate=0.06, tenant_id=t.id, project_id=p1.id)
        r2 = Resource(name='orders-db', type='db', size='medium', base_rate=None, tenant_id=t.id, project_id=p1.id)
        r3 = Resource(name='warehouse-cache', type='cache', size='small', base_rate=None, tenant_id=t.id, project_id=p2.id)
        db.session.add_all([r1, r2, r3])
        db.session.flush()

        upsert_tags(r1, {'environment': 'prod', 'cost-center': 'web', 'priority': 'high'})
        upsert_tags(r2, {'environment': 'prod', 'cost-center': 'db'})
        upsert_tags(r3, {'environment': 'staging', 'priority': 'low'})
        db.session.commit()
        print('Seeded sample data')
    else:
        print('Sample data already exists')

