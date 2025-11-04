from __future__ import annotations
import json
import os
from pathlib import Path
import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from alembic.runtime.migration import MigrationContext

app = typer.Typer(add_completion=False)


def alembic_config() -> Config:
    cfg = Config("alembic.ini")
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _current_revision() -> str | None:
    from app.db import get_database_url
    engine = create_engine(get_database_url(), future=True)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


def _head_revision(cfg: Config) -> str:
    script_dir = cfg.get_main_option("script_location")
    # naive: read heads from alembic's script directory
    from alembic.script import ScriptDirectory
    script = ScriptDirectory(script_dir)
    return script.get_current_head()


@app.command()
def upgrade(target: str = typer.Argument("head")):
    """Upgrade to target (default: head)."""
    cfg = alembic_config()
    command.upgrade(cfg, target)


@app.command()
def downgrade(target: str = typer.Argument("-1")):
    """Downgrade to target (default: -1)."""
    cfg = alembic_config()
    command.downgrade(cfg, target)


@app.command("current")
def current_cmd():
    rev = _current_revision()
    typer.echo(rev or "<none>")


STABLE_FILE = Path("releases/stable.json")


def _read_stable() -> dict:
    if STABLE_FILE.exists():
        return json.loads(STABLE_FILE.read_text())
    return {"stable": None}


def _write_stable(data: dict) -> None:
    STABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STABLE_FILE.write_text(json.dumps(data, indent=2))


@app.command("mark-stable")
def mark_stable():
    cfg = alembic_config()
    head = _head_revision(cfg)
    state = _read_stable()
    state["stable"] = head
    _write_stable(state)
    typer.echo(f"Marked stable: {head}")


@app.command("rollback-to-stable")
def rollback_to_stable():
    cfg = alembic_config()
    state = _read_stable()
    stable = state.get("stable")
    if not stable:
        raise typer.Exit(code=2)
    command.downgrade(cfg, stable)
    typer.echo(f"Downgraded to stable: {stable}")


if __name__ == "__main__":
    app()

