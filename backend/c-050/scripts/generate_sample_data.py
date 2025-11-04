import os
import sys
import click

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services.sample_data import generate_sample_data  # noqa: E402


@click.command()
@click.option('--users', default=10, show_default=True, help='Number of users to generate')
@click.option('--products', default=15, show_default=True, help='Number of products to generate')
@click.option('--orders', default=20, show_default=True, help='Number of orders to generate')
@click.option('--seed', default=None, type=int, help='Random seed for reproducibility')
@click.option('--database-url', envvar='DATABASE_URL', default=None, help='Database URL (overrides config)')
def main(users, products, orders, seed, database_url):
    """Generate sample data into the configured database."""
    from config import Config

    class _Cfg(Config):
        if database_url:
            SQLALCHEMY_DATABASE_URI = database_url

    app = create_app(_Cfg)
    with app.app_context():
        click.echo(f"Generating sample data: users={users}, products={products}, orders={orders}, seed={seed}")
        stats = generate_sample_data(users=users, products=products, orders=orders, seed=seed)
        click.echo(f"Done. Inserted: {stats}")


if __name__ == '__main__':
    main()

