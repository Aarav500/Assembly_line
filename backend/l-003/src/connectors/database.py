from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from typing import Any, Dict, List
from .base import BaseConnector


class DatabaseConnector(BaseConnector):
    slug = "database"
    name = "Database"

    def _check_enabled(self) -> bool:
        return bool(self.config.get("DATABASE_URL"))

    def _engine(self) -> Engine:
        return create_engine(self.config.get("DATABASE_URL"), pool_pre_ping=True, future=True)

    def health(self) -> Dict[str, Any]:
        try:
            with self._engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def op_list_tables(self) -> Dict[str, Any]:
        engine = self._engine()
        insp = inspect(engine)
        schemas = insp.get_schema_names()
        tables = {}
        for schema in schemas:
            try:
                tables[schema] = insp.get_table_names(schema=schema)
            except Exception:
                # Some dialects may not support schema listing
                pass
        return {"schemas": schemas, "tables": tables}

    def op_select(self, query: str, params: Dict[str, Any] = None, limit: int = 1000):
        if not query or not query.strip().lower().startswith("select"):
            raise ValueError("Only SELECT queries are allowed")
        engine = self._engine()
        with engine.connect() as conn:
            stmt = text(query)
            if limit and "limit" not in query.lower():
                # Wrap with outer select to enforce limit when possible
                stmt = text(f"SELECT * FROM (" + query + ") __sub__ LIMIT :__limit")
                exec_params = (params or {}) | {"__limit": limit}
            else:
                exec_params = params or {}
            result = conn.execute(stmt, exec_params)
            rows = [dict(r._mapping) for r in result]
        return {"row_count": len(rows), "rows": rows}

    def op_execute_raw_select(self, query: str, params: Dict[str, Any] = None):
        if not self.config.get("ALLOW_DB_RAW_SELECT", False):
            raise ValueError("Raw SELECT execution not allowed. Enable ALLOW_DB_RAW_SELECT=true to use.")
        return self.op_select(query=query, params=params, limit=None)

