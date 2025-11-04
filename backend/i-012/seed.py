from app import create_app
from models import db, User, Project, ProjectMember, Role, ensure_seed_data
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()
    ensure_seed_data()

    # Users
    alice = User(username='alice', password_hash=generate_password_hash('alice123'), is_admin=True)
    bob = User(username='bob', password_hash=generate_password_hash('bob123'))
    carol = User(username='carol', password_hash=generate_password_hash('carol123'))
    db.session.add_all([alice, bob, carol])
    db.session.commit()

    # Projects
    proj1 = Project(name='Apollo', description='Lunar mission control system')
    proj2 = Project(name='Zephyr', description='Wind farm monitoring')
    db.session.add_all([proj1, proj2])
    db.session.commit()

    # Roles
    owner = Role.query.filter_by(name='Owner').first()
    maint = Role.query.filter_by(name='Maintainer').first()
    viewer = Role.query.filter_by(name='Viewer').first()

    # Memberships
    db.session.add_all([
        ProjectMember(project_id=proj1.id, user_id=alice.id, role_id=owner.id),
        ProjectMember(project_id=proj1.id, user_id=bob.id, role_id=maint.id),
        ProjectMember(project_id=proj2.id, user_id=carol.id, role_id=viewer.id)
    ])
    db.session.commit()

    print('Database seeded. Users: alice/alice123 (admin), bob/bob123, carol/carol123')

