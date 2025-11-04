import os
import sys
import click

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import create_app  # noqa: E402
from app.services.exporter import export_data  # noqa: E402


@click.command()
@click.option('--format', 'fmt', type=click.Choice(['json', 'csv', 'both']), default='both', show_default=True)
@click.option('--out-dir', default='exports', show_default=True, help='Base output directory')
@click.option('--database-url', envvar='DATABASE_URL', default=None, help='Database URL (overrides config)')
def main(fmt, out_dir, database_url):
    """Export dataset from the database to JSON/CSV files."""
    from config import Config

    class _Cfg(Config):
        if database_url:
            SQLALCHEMY_DATABASE_URI = database_url

    app = create_app(_Cfg)
    with app.app_context():
        click.echo(f"Exporting data in format={fmt} to {out_dir} ...")
        result = export_data(fmt=fmt, out_base=out_dir)
        click.echo(f"Done. {result}")


if __name__ == '__main__':
    main()

