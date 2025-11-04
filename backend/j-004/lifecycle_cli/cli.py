import json
import sys
import click
from pathlib import Path

from . import __version__
from .utils import echo_info, echo_warn, echo_err
from .analysis import analyze_project
from .generator import generate_openapi_spec, generate_dockerfile
from .deployer import create_scaffold, deploy_release, rollback_release


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(version=__version__, prog_name="lifecycle")
def cli():
    """Lifecycle CLI: create, analyze, generate, deploy, rollback."""


@cli.command()
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--name", default="my_flask_app", help="Application name for the scaffold")
@click.option("--force", is_flag=True, help="Overwrite if path exists and is non-empty")
def create(path: Path, name: str, force: bool):
    """Create a new Flask app scaffold at PATH."""
    try:
        created = create_scaffold(path, app_name=name, force=force)
    except Exception as e:
        echo_err(f"Create failed: {e}")
        sys.exit(1)
    echo_info(f"Created scaffold at {created}")


@cli.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--json-out", type=click.Path(path_type=Path), help="Write analysis result to JSON file")
def analyze(path: Path, json_out: Path | None):
    """Analyze a project at PATH and print JSON report."""
    try:
        report = analyze_project(path)
    except Exception as e:
        echo_err(f"Analyze failed: {e}")
        sys.exit(1)
    payload = json.dumps(report, indent=2)
    if json_out:
        json_out.write_text(payload, encoding="utf-8")
        echo_info(f"Analysis written to {json_out}")
    else:
        click.echo(payload)


@cli.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--openapi", type=click.Path(path_type=Path), help="Path to write generated OpenAPI-like spec JSON")
@click.option("--dockerfile", is_flag=True, help="Generate a Dockerfile from template")
@click.option("--force", is_flag=True, help="Overwrite existing generated files if present")
def generate(path: Path, openapi: Path | None, dockerfile: bool, force: bool):
    """Generate artifacts (OpenAPI spec, Dockerfile) for PATH."""
    try:
        if openapi:
            out = generate_openapi_spec(path)
            openapi.write_text(json.dumps(out, indent=2), encoding="utf-8")
            echo_info(f"OpenAPI-like spec written to {openapi}")
        if dockerfile:
            df_path = generate_dockerfile(path, overwrite=force)
            echo_info(f"Dockerfile written to {df_path}")
        if not openapi and not dockerfile:
            echo_warn("Nothing to generate. Use --openapi or --dockerfile.")
    except Exception as e:
        echo_err(f"Generate failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--keep", default=5, show_default=True, type=int, help="Number of releases to retain")
@click.option("--no-start", is_flag=True, help="Prepare release but do not start server")
@click.option("--env", default="production", show_default=True, help="Environment label for deployment")
def deploy(path: Path, host: str, port: int, keep: int, no_start: bool, env: str):
    """Deploy the project at PATH, snapshotting a release and starting a server."""
    try:
        result = deploy_release(path, host=host, port=port, keep=keep, start=not no_start, env=env)
    except Exception as e:
        echo_err(f"Deploy failed: {e}")
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--steps", default=1, show_default=True, type=int, help="How many releases to roll back")
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=None, type=int, help="Override port when restarting previous release")
def rollback(path: Path, steps: int, host: str, port: int | None):
    """Rollback deployment at PATH to a previous release and restart it."""
    try:
        result = rollback_release(path, steps=steps, host=host, port=port)
    except Exception as e:
        echo_err(f"Rollback failed: {e}")
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


def main():
    cli(prog_name="lifecycle")

