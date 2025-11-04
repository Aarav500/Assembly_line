import click
from flask.cli import with_appcontext

from extensions import db
from models import Plan, Tenant
import secrets
from datetime import date


@click.command('seed')
@with_appcontext
def seed():
    # Create default plans
    if Plan.query.count() == 0:
        basic = Plan(
            name='Basic',
            price_cents=1999,
            included_quotas={'api_calls': 10000},
            overage_rates={'api_calls': 1},
        )
        pro = Plan(
            name='Pro',
            price_cents=9999,
            included_quotas={'api_calls': 200000},
            overage_rates={'api_calls': 1},
        )
        db.session.add_all([basic, pro])
        db.session.commit()
        click.echo('Created default plans: Basic, Pro')

    if Tenant.query.count() == 0:
        plan = Plan.query.filter_by(name='Basic').first()
        t = Tenant(
            name='Acme Inc',
            slug='acme',
            api_key=secrets.token_hex(24),
            plan=plan,
            config={'features': {'beta': False}, 'limits': {'api_calls': 15000}, 'limit_behavior': 'overage'},
            billing_cycle_anchor=date.today().replace(day=min(date.today().day, 28)),
        )
        db.session.add(t)
        db.session.commit()
        click.echo(f'Created sample tenant: {t.name} (api_key={t.api_key})')

