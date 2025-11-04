from flask import current_app
from flask.cli import with_appcontext
import click
from .extensions import db
from .models import Role, User, Profile


def register_cli(app):
    @app.cli.command('init-roles')
    @with_appcontext
    def init_roles():
        names = ['admin', 'user']
        for name in names:
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, description=f"{name} role"))
        db.session.commit()
        click.echo('Roles initialized.')

    @app.cli.command('create-superuser')
    @click.option('--email', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    @with_appcontext
    def create_superuser(email, password):
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            click.echo('User already exists')
            return
        user = User(email=email, is_active=True, is_email_verified=True)
        user.set_password(password)
        profile = Profile(user=user, full_name='Administrator')
        db.session.add(user)
        db.session.add(profile)
        admin = Role.query.filter_by(name='admin').first()
        if not admin:
            admin = Role(name='admin', description='Administrator')
            db.session.add(admin)
            db.session.commit()
        user.roles.append(admin)
        user_role = Role.query.filter_by(name='user').first()
        if user_role:
            user.roles.append(user_role)
        db.session.commit()
        click.echo('Superuser created')

