from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine


SYSTEM_SCHEMAS = {
    "postgresql": {"pg_catalog", "information_schema"},
    "mysql": {"information_schema", "performance_schema", "mysql", "sys"},
    "mariadb": {"information_schema", "performance_schema", "mysql", "sys"},
    "mssql": {"INFORMATION_SCHEMA", "sys"},
    "sqlite": {"main", "temp"},
    "oracle": {"SYSTEM", "SYS"},
}


@contextmanager
def _engine(db_url: str) -> Engine:
    engine = create_engine(db_url)
    try:
        yield engine
    finally:
        engine.dispose()


def _collect_schemas(inspector, requested: Optional[Iterable[str]], exclude_system: bool) -> List[str]:
    all_schemas = list(inspector.get_schema_names() or [])
    dialect = inspector.bind.dialect.name if inspector.bind is not None else ""
    sys_schemas: Set[str] = SYSTEM_SCHEMAS.get(dialect, set()) if exclude_system else set()
    if requested:
        wanted = set(requested)
        return [s for s in all_schemas if s in wanted]
    return [s for s in all_schemas if s not in sys_schemas]


def _get_server_version(inspector) -> Optional[str]:
    try:
        d = inspector.bind.dialect  # type: ignore[attr-defined]
        v = getattr(d, "server_version_info", None)
        if v:
            try:
                return ".".join(str(p) for p in v)
            except Exception:
                return str(v)
    except Exception:
        pass
    return None


def _normalize_column(col: Dict[str, Any]) -> Dict[str, Any]:
    typ = col.get("type")
    type_str = str(typ) if typ is not None else None
    return {
        "name": col.get("name"),
        "type": type_str,
        "nullable": bool(col.get("nullable", True)),
        "default": col.get("default"),
        "autoincrement": col.get("autoincrement"),
        "comment": col.get("comment"),
        "length": getattr(typ, "length", None) if typ is not None else None,
        "precision": getattr(typ, "precision", None) if typ is not None else None,
        "scale": getattr(typ, "scale", None) if typ is not None else None,
    }


def _normalize_fk(fk: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": fk.get("name"),
        "constrained_columns": fk.get("constrained_columns", []),
        "referred_schema": fk.get("referred_schema"),
        "referred_table": fk.get("referred_table"),
        "referred_columns": fk.get("referred_columns", []),
        "options": {
            "onupdate": fk.get("options", {}).get("onupdate") if fk.get("options") else fk.get("onupdate"),
            "ondelete": fk.get("options", {}).get("ondelete") if fk.get("options") else fk.get("ondelete"),
            "deferrable": fk.get("deferrable"),
            "initially": fk.get("initially"),
        },
    }


def introspect_database(
    db_url: str,
    schemas: Optional[Iterable[str]] = None,
    include_views: bool = True,
    exclude_system_schemas: bool = True,
) -> Dict[str, Any]:
    with _engine(db_url) as engine:
        insp = inspect(engine)
        dialect = insp.bind.dialect.name  # type: ignore[attr-defined]
        driver = insp.bind.dialect.driver  # type: ignore[attr-defined]
        server_version = _get_server_version(insp)

        result: Dict[str, Any] = {
            "dialect": dialect,
            "driver": driver,
            "server_version": server_version,
            "schemas": {},
        }

        for schema in _collect_schemas(insp, schemas, exclude_system_schemas):
            schema_obj: Dict[str, Any] = {"entities": {}}

            # Tables
            for table_name in insp.get_table_names(schema=schema):
                cols = [_normalize_column(c) for c in insp.get_columns(table_name, schema=schema)]
                try:
                    pk = insp.get_pk_constraint(table_name, schema=schema) or {}
                except NotImplementedError:
                    pk = {}
                try:
                    fks = [_normalize_fk(fk) for fk in insp.get_foreign_keys(table_name, schema=schema)]
                except NotImplementedError:
                    fks = []
                try:
                    uniques = insp.get_unique_constraints(table_name, schema=schema)
                except NotImplementedError:
                    uniques = []
                try:
                    idx = insp.get_indexes(table_name, schema=schema)
                except NotImplementedError:
                    idx = []
                try:
                    comment = insp.get_table_comment(table_name, schema=schema).get("text")
                except Exception:
                    comment = None

                schema_obj["entities"][table_name] = {
                    "name": table_name,
                    "schema": schema,
                    "is_view": False,
                    "columns": cols,
                    "primary_key": {
                        "name": pk.get("name"),
                        "columns": pk.get("constrained_columns", []) or pk.get("columns", []),
                    },
                    "foreign_keys": fks,
                    "unique_constraints": [
                        {"name": u.get("name"), "columns": u.get("column_names", [])} for u in uniques
                    ],
                    "indexes": [
                        {
                            "name": i.get("name"),
                            "columns": i.get("column_names", []),
                            "unique": bool(i.get("unique", False)),
                        }
                        for i in idx
                    ],
                    "comment": comment,
                }

            # Views
            if include_views:
                try:
                    views = insp.get_view_names(schema=schema)
                except NotImplementedError:
                    views = []
                for view_name in views:
                    cols = [_normalize_column(c) for c in insp.get_columns(view_name, schema=schema)]
                    try:
                        comment = insp.get_table_comment(view_name, schema=schema).get("text")
                    except Exception:
                        comment = None
                    schema_obj["entities"][view_name] = {
                        "name": view_name,
                        "schema": schema,
                        "is_view": True,
                        "columns": cols,
                        "primary_key": {"name": None, "columns": []},
                        "foreign_keys": [],
                        "unique_constraints": [],
                        "indexes": [],
                        "comment": comment,
                    }

            result["schemas"][schema] = schema_obj

        return result

