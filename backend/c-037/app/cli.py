import click
from flask import current_app

from .tenancy import (
    sanitize_tenant_id,
    schema_for_tenant,
    ensure_schema,
    drop_schema,
    create_all_in_schema,
    list_tenant_schemas,
)


def register_cli(app):
    @app.cli.group("tenants")
    def tenants_group():
        """Manage tenants (schema-per-tenant)."""
        pass

    @tenants_group.command("create")
    @click.argument("tenant_id")
    @click.option("--init-db/--no-init-db", default=True, help="Create tables after schema creation")
    def create_tenant(tenant_id: str, init_db: bool):
        tid = sanitize_tenant_id(tenant_id)
        schema = schema_for_tenant(tid)
        click.echo(f"Creating tenant '{tid}' with schema '{schema}' ...")
        ensure_schema(schema)
        if init_db:
            create_all_in_schema(schema)
        click.echo("Done.")

    @tenants_group.command("drop")
    @click.argument("tenant_id")
    @click.option("--force", is_flag=True, default=False, help="Drop schema even if it contains objects")
    def drop_tenant(tenant_id: str, force: bool):
        tid = sanitize_tenant_id(tenant_id)
        schema = schema_for_tenant(tid)
        click.echo(f"Dropping tenant '{tid}' schema '{schema}' (cascade={force}) ...")
        drop_schema(schema, cascade=force)
        click.echo("Done.")

    @tenants_group.command("init-db")
    @click.argument("tenant_id")
    def init_db(tenant_id: str):
        tid = sanitize_tenant_id(tenant_id)
        schema = schema_for_tenant(tid)
        click.echo(f"Initializing DB objects in schema '{schema}' ...")
        create_all_in_schema(schema)
        click.echo("Done.")

    @tenants_group.command("list")
    @click.option("--prefix", default=None, help="Schema prefix filter")
    def list_tenants(prefix: str | None):
        schemas = list_tenant_schemas(prefix)
        pref = prefix or current_app.config.get("TENANT_SCHEMA_PREFIX", "t_")
        click.echo(f"Schemas with prefix '{pref}':")
        for s in schemas:
            click.echo(f"- {s}")

    @tenants_group.command("ensure")
    @click.argument("tenant_id")
    def ensure(tenant_id: str):
        tid = sanitize_tenant_id(tenant_id)
        schema = schema_for_tenant(tid)
        click.echo(f"Ensuring schema '{schema}' exists...")
        ensure_schema(schema)
        click.echo("Done.")

