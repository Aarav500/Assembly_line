from typing import Tuple, List
import sqlparse
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config import Config


def _get_engine_for_env(env: str) -> Engine:
    url = Config.TARGET_DBS.get(env)
    if not url:
        raise ValueError(f"No target DB URL configured for env '{env}'")
    engine = create_engine(url, future=True)
    return engine


def _split_statements(sql: str) -> List[str]:
    return [s.strip() for s in sqlparse.split(sql) if s and s.strip()]


def dry_run(sql: str, env: str) -> Tuple[bool, str]:
    engine = _get_engine_for_env(env)
    stmts = _split_statements(sql or "")
    log_lines = []
    try:
        with engine.begin() as conn:
            # Use a savepoint to ensure rollback even if autocommit behavior differs
            trans = conn.begin_nested()
            try:
                for i, stmt in enumerate(stmts, start=1):
                    log_lines.append(f"[DRY-RUN] Executing statement {i}: {stmt[:200]}{'...' if len(stmt)>200 else ''}")
                    if stmt.lower().startswith("commit") or stmt.lower().startswith("begin") or stmt.lower().startswith("rollback"):
                        log_lines.append(f"[DRY-RUN] Skipping transaction control statement {i}")
                        continue
                    conn.execute(text(stmt))
                # force rollback
                trans.rollback()
                log_lines.append("[DRY-RUN] Rolled back savepoint; no changes applied")
            except Exception as e:
                try:
                    if trans.is_active:
                        trans.rollback()
                except Exception:
                    pass
                log_lines.append(f"[DRY-RUN][ERROR] {e}")
                return False, "\n".join(log_lines)
    except SQLAlchemyError as e:
        log_lines.append(f"[DRY-RUN][ENGINE][ERROR] {e}")
        return False, "\n".join(log_lines)
    return True, "\n".join(log_lines)


def apply(sql: str, env: str) -> Tuple[bool, str]:
    engine = _get_engine_for_env(env)
    stmts = _split_statements(sql or "")
    log_lines = []
    try:
        with engine.begin() as conn:
            for i, stmt in enumerate(stmts, start=1):
                log_lines.append(f"[APPLY] Executing statement {i}: {stmt[:200]}{'...' if len(stmt)>200 else ''}")
                if stmt.lower().startswith("commit") or stmt.lower().startswith("begin") or stmt.lower().startswith("rollback"):
                    log_lines.append(f"[APPLY] Skipping transaction control statement {i}")
                    continue
                conn.execute(text(stmt))
        log_lines.append("[APPLY] Committed migration")
    except SQLAlchemyError as e:
        log_lines.append(f"[APPLY][ERROR] {e}")
        return False, "\n".join(log_lines)
    return True, "\n".join(log_lines)

