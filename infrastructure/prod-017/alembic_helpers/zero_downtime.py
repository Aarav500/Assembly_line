from __future__ import annotations
from typing import Iterable, Optional
from alembic import op
import sqlalchemy as sa


def _quote_ident(name: str) -> str:
    # Simple identifier quoting; assumes valid, not schema-qualified
    return '"' + name.replace('"', '""') + '"'


def create_index_concurrently(
    index_name: str,
    table_name: str,
    columns: Iterable[str],
    unique: bool = False,
    where: Optional[str] = None,
    if_not_exists: bool = True,
) -> None:
    cols = ", ".join(_quote_ident(c) for c in columns)
    ine = " IF NOT EXISTS" if if_not_exists else ""
    uq = "UNIQUE " if unique else ""
    where_sql = f" WHERE {where}" if where else ""
    sql = (
        f"CREATE {uq}INDEX CONCURRENTLY{ine} {_quote_ident(index_name)} ON {_quote_ident(table_name)} ({cols}){where_sql};"
    )
    ctx = op.get_context()
    # CONCURRENTLY must run outside a transaction. Use Alembic autocommit block.
    with ctx.autocommit_block():
        op.execute(sa.text(sql))


def drop_index_concurrently(index_name: str, if_exists: bool = True) -> None:
    ie = " IF EXISTS" if if_exists else ""
    sql = f"DROP INDEX CONCURRENTLY{ie} {_quote_ident(index_name)};"
    ctx = op.get_context()
    with ctx.autocommit_block():
        op.execute(sa.text(sql))


def add_check_not_valid(table_name: str, constraint_name: str, check_sql: str) -> None:
    sql = (
        f"ALTER TABLE {_quote_ident(table_name)} "
        f"ADD CONSTRAINT {_quote_ident(constraint_name)} CHECK ({check_sql}) NOT VALID;"
    )
    op.execute(sa.text(sql))


def validate_constraint(table_name: str, constraint_name: str) -> None:
    sql = (
        f"ALTER TABLE {_quote_ident(table_name)} VALIDATE CONSTRAINT {_quote_ident(constraint_name)};"
    )
    op.execute(sa.text(sql))


def set_not_null(table_name: str, column_name: str) -> None:
    sql = (
        f"ALTER TABLE {_quote_ident(table_name)} ALTER COLUMN {_quote_ident(column_name)} SET NOT NULL;"
    )
    op.execute(sa.text(sql))


def drop_not_null(table_name: str, column_name: str) -> None:
    sql = (
        f"ALTER TABLE {_quote_ident(table_name)} ALTER COLUMN {_quote_ident(column_name)} DROP NOT NULL;"
    )
    op.execute(sa.text(sql))


def add_column_nullable(
    table_name: str,
    column: sa.Column,
    create_default_for_future: bool = False,
) -> None:
    # Avoid server_default on add to prevent table rewrite; set default after if needed
    op.add_column(table_name, column)
    if create_default_for_future and column.server_default is not None:
        default_sql = column.server_default.arg if isinstance(column.server_default, sa.text) else column.server_default.arg
        sql = (
            f"ALTER TABLE {_quote_ident(table_name)} ALTER COLUMN {_quote_ident(column.name)} SET DEFAULT {default_sql};"
        )
        op.execute(sa.text(sql))


def drop_column_safely(table_name: str, column_name: str) -> None:
    # Use contract phase for drops
    op.drop_column(table_name, column_name)

