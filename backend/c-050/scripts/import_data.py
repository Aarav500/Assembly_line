import os
import sys
import click

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import create_app  # noqa: E402
from app.services.importer import import_data  # noqa: E402


@click.command()
@click.option('--format', 'fmt', type=click.Choice(['json', 'csv']), default='json', show_default=True)
@click.option('--from-dir', required=True, help='Directory containing exported files')
@click.option('--no-reset', is_flag=True, default=False, help='Do not reset database before import')
@click.option('--database-url', envvar='DATABASE_URL', default=None, help='Database URL (overrides config)')
def main(fmt, from_dir, no_reset, database_url):
    """Import dataset from JSON/CSV exports into the database."""
    from config import Config

    class _Cfg(Config):
        if database_url:
            SQLALCHEMY_DATABASE_URI = database_url

    app = create_app(_Cfg)
    with app.app_context():
        click.echo(f"Importing {fmt} from {from_dir} (reset={'no' if no_reset else 'yes'}) ...")
        result = import_data(fmt=fmt, from_dir=from_dir, reset=not no_reset)
        click.echo(f"Done. {result}")


if __name__ == '__main__':
    main()

