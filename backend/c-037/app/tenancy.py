import re
from typing import Optional

from flask import current_app, g, request
from sqlalchemy import text

from .db import db


SAFE_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")


def sanitize_tenant_id(tenant_id: str) -> str:
    if not tenant_id:
        raise ValueError("empty tenant id")
    tid = SAFE_IDENT_RE.sub("_", tenant_id.strip())
    # PostgreSQL identifier max length is 63
    return tid[:63].lower()


def schema_for_tenant(tenant_id: str) -> str:
    prefix = current_app.config.get("TENANT_SCHEMA_PREFIX", "t_")
    return f"{prefix}{sanitize_tenant_id(tenant_id)}"


def quote_ident(ident: str) -> str:
    # Basic quoting for PostgreSQL identifiers
    return '"' + ident.replace('"', '""') + '"'


def resolve_tenant_id(req) -> Optional[str]:
    header_name = current_app.config.get("TENANT_HEADER", "X-Tenant")
    tenant_id = req.headers.get(header_name)
    if tenant_id:
        return tenant_id
    # Optional fallback to subdomain, e.g., tenant.example.com
    host = req.host.split(":")[0]
    parts = host.split(".")
    if len(parts) > 2:
        return parts[0]
    # Optional default tenant
    return current_app.config.get("TENANT_DEFAULT")


def set_tenant_on_request() -> None:
    tenant_id = resolve_tenant_id(request)
    g.tenant_id = tenant_id
    if tenant_id is None:
        return
    schema = schema_for_tenant(tenant_id)
    g.tenant_schema = schema
    # Set per-request search_path; LOCAL confines it to the current transaction
    qp = f"SET LOCAL search_path TO {quote_ident(schema)}, public"
    db.session.execute(text(qp))


def ensure_schema(schema: str) -> None:
    with db.engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(schema)}")


def drop_schema(schema: str, cascade: bool = True) -> None:
    with db.engine.begin() as conn:
        if cascade:
            conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {quote_ident(schema)} CASCADE")
        else:
            conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {quote_ident(schema)}")


def create_all_in_schema(schema: str) -> None:
    from .models import db as _db  # ensure models are imported

    with db.engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(schema)}")
        conn.exec_driver_sql(f"SET search_path TO {quote_ident(schema)}, public")
        _db.metadata.create_all(conn)


def list_tenant_schemas(prefix: Optional[str] = None) -> list[str]:
    if prefix is None:
        prefix = current_app.config.get("TENANT_SCHEMA_PREFIX", "t_")
    with db.engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name LIKE :pattern
                ORDER BY 1
                """
            ),
            {"pattern": f"{prefix}%"},
        )
        return [row[0] for row in res]

