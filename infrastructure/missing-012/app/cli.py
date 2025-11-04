import click
from flask import Flask
from .extensions import db
from .models import User, NotificationPreferences, NotificationEvent
from .services.notification_service import service


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create database tables"""
        with app.app_context():
            db.create_all()
        click.echo("Database initialized")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Seed demo user and preferences"""
        with app.app_context():
            u = User(email="demo@example.com", phone="+15550000001", push_token="push-token-demo", timezone="UTC")
            db.session.add(u)
            db.session.flush()
            p = NotificationPreferences(user_id=u.id, email_enabled=True, sms_enabled=False, push_enabled=True, frequency="daily", digest_enabled=True)
            db.session.add(p)
            db.session.commit()
        click.echo(f"Seeded demo user id={u.id}")

    @app.cli.command("digest-run")
    @click.option("--user-id", type=int, default=None)
    def digest_run(user_id: int | None):
        with app.app_context():
            res = service.run_due_digests(user_id=user_id)
            click.echo(res)

