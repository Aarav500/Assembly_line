from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Iterable

import click
from flask import Flask


def sample_docs(n: int = 5) -> Iterable[dict]:
    base = datetime.utcnow()
    for i in range(n):
        yield {
            "id": i + 1,
            "title": f"Document {i+1}",
            "content": f"This is a sample document number {i+1} for testing full text search integration.",
            "tags": ["sample", "test", "doc", f"tag{i%3}"],
            "created_at": (base - timedelta(days=i)).isoformat(),
        }


def init_app(app: Flask) -> None:
    @app.cli.command("search-ping")
    def search_ping():
        """Ping the search backend."""
        ok = app.extensions["search"].ping()
        click.echo("ok" if ok else "unreachable")

    @app.cli.command("search-init")
    @click.argument("index", required=False)
    def search_init(index: str | None):
        """Create the index with default schema/settings."""
        idx = index or app.config.get("DEFAULT_INDEX_NAME", "documents")
        res = app.extensions["search"].create_index(idx)
        click.echo(json.dumps(res, indent=2))

    @app.cli.command("search-delete")
    @click.argument("index", required=False)
    def search_delete(index: str | None):
        """Delete the index."""
        idx = index or app.config.get("DEFAULT_INDEX_NAME", "documents")
        res = app.extensions["search"].delete_index(idx)
        click.echo(json.dumps(res, indent=2))

    @app.cli.command("search-reindex-sample")
    @click.argument("index", required=False)
    @click.option("--count", "count", default=10, help="Number of sample docs")
    def search_reindex_sample(index: str | None, count: int):
        """Index sample data for quick testing."""
        idx = index or app.config.get("DEFAULT_INDEX_NAME", "documents")
        app.extensions["search"].create_index(idx)
        res = app.extensions["search"].bulk_index(idx, sample_docs(count))
        click.echo(json.dumps(res, indent=2))


