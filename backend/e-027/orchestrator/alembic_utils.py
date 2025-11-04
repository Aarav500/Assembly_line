from __future__ import annotations
import os
import re
import time
from typing import Any
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine

from settings import settings


def get_alembic_config() -> Config:
    cfg = Config(settings.ALEMBIC_INI_PATH)
    # ensure script_location resolves correctly when invoked programmatically
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return cfg


def get_script_directory(cfg: Config) -> ScriptDirectory:
    return ScriptDirectory.from_config(cfg)


def get_current_revision(engine: Engine) -> str | None:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            if not rows:
                return None
            if len(rows) > 1:
                # multiple heads; simplify by returning first
                return rows[0][0]
            return rows[0][0]
    except Exception:
        return None


def get_head_revisions(cfg: Config) -> list[str]:
    script = get_script_directory(cfg)
    return list(script.get_heads())


def load_all_revisions(cfg: Config) -> list[dict[str, Any]]:
    script = get_script_directory(cfg)
    revs = []
    for rev in script.walk_revisions(base="base", head="heads"):
        # walk_revisions yields from head to base; we'll normalize later
        path = rev.path
        entry = {
            "revision": rev.revision,
            "down_revision": rev.down_revision,
            "doc": rev.doc,
            "path": path,
        }
        # Extract PHASE from file content for safety rules
        try:
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            m = re.search(r"^\s*PHASE\s*=\s*['\"](\w+)['\"]", src, flags=re.MULTILINE)
            phase = m.group(1) if m else None
            entry["phase"] = phase
            entry["source"] = src
        except Exception:
            entry["phase"] = None
            entry["source"] = None
        revs.append(entry)
    # Return from base to head order
    return list(reversed(revs))


def build_linear_chain(revisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Build mapping for linear chain determination
    by_rev = {r["revision"]: r for r in revisions}
    # find base (down_revision is None)
    base = None
    for r in revisions:
        if r["down_revision"] in (None, (), []):
            base = r
            break
    if not base:
        return revisions
    # Construct chain forward
    chain = [base]
    next_rev = True
    while next_rev:
        next_rev = None
        for r in revisions:
            if r["down_revision"] == chain[-1]["revision"]:
                next_rev = r
                chain.append(r)
                break
    # If not all revisions are in chain, there are branches; return full list in given order
    if len(chain) != len(revisions):
        return revisions
    return chain


def list_pending_revisions(engine: Engine, cfg: Config) -> list[dict[str, Any]]:
    all_revs = load_all_revisions(cfg)
    chain = build_linear_chain(all_revs)
    current = get_current_revision(engine)
    if current is None:
        return chain
    pending = []
    seen_current = False
    for r in chain:
        if seen_current:
            pending.append(r)
        elif r["revision"] == current:
            seen_current = True
    return pending


UNSAFE_PATTERNS = [
    (re.compile(r"op\.drop_(table|column)\s*\("), "drop_table_or_column", "Dropping tables/columns can break running code"),
    (re.compile(r"op\.alter_column\s*\([^\)]*nullable\s*=\s*False"), "set_not_null", "Setting NOT NULL can lock large tables and break writers"),
    (re.compile(r"op\.rename_(table|column)\s*\("), "rename", "Renaming breaks running code unless dual-read handled"),
    (re.compile(r"op\.execute\s*\(.*LOCK\s+TABLE", re.IGNORECASE | re.DOTALL), "explicit_lock", "Explicit table locks can cause downtime"),
]

WARNING_PATTERNS = [
    (re.compile(r"op\.create_index\s*\([^\)]*\)"), "index_no_concurrently", "Index creation should be concurrent on large tables (postgresql_concurrently=True)"),
    (re.compile(r"op\.create_foreign_key\s*\("), "fk_validation", "Foreign key creation can lock; consider deferrable=True, initially='DEFERRED'"),
]


def analyze_migration_source(src: str, phase: str | None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for regex, code, message in UNSAFE_PATTERNS:
        if regex.search(src or ""):
            if (phase or "expand").lower() != "contract":
                errors.append({"code": code, "message": message})
            else:
                # contract phase allows unsafe operations by design
                warnings.append({"code": code, "message": f"Unsafe operation allowed in contract phase: {message}"})
    for regex, code, message in WARNING_PATTERNS:
        if regex.search(src or ""):
            # If it already specifies concurrently=True, suppress index warning
            if code == "index_no_concurrently" and re.search(r"postgresql_concurrently\s*=\s*True", src or ""):
                continue
            warnings.append({"code": code, "message": message})
    return {"errors": errors, "warnings": warnings}


def analyze_pending(engine: Engine, cfg: Config) -> list[dict[str, Any]]:
    pending = list_pending_revisions(engine, cfg)
    analyzed: list[dict[str, Any]] = []
    for r in pending:
        res = analyze_migration_source(r.get("source", ""), r.get("phase"))
        analyzed.append({
            "revision": r["revision"],
            "down_revision": r["down_revision"],
            "doc": r["doc"],
            "path": r["path"],
            "phase": r.get("phase"),
            "errors": res["errors"],
            "warnings": res["warnings"],
        })
    return analyzed


def acquire_advisory_lock(engine: Engine, lock_id: int) -> bool:
    with engine.connect() as conn:
        got = conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar()
        return bool(got)


def release_advisory_lock(engine: Engine, lock_id: int) -> bool:
    with engine.connect() as conn:
        rel = conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id}).scalar()
        return bool(rel)


def upgrade_head(cfg: Config) -> None:
    command.upgrade(cfg, "head")


def current_as_string(cfg: Config) -> str:
    # For logging only; not used for logic
    from io import StringIO
    buf = StringIO()
    cfg.print_stdout = buf.write  # type: ignore
    command.current(cfg, verbose=False)
    return buf.getvalue().strip()

