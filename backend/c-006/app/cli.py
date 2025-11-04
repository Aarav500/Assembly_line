import click
from flask import current_app
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy import text
from .extensions import db
from .models import User, Post  # ensure models are imported so metadata is populated


def register_cli(app):
    @app.cli.command("db-seed")
    @click.option("--users", default=3, show_default=True, help="Number of users")
    @click.option("--posts", default=2, show_default=True, help="Posts per user")
    def seed(users: int, posts: int):
        """Seed the database with sample data."""
        from .models import User, Post

        for i in range(1, users + 1):
            u = User(email=f"user{i}@example.com", name=f"User {i}")
            db.session.add(u)
            db.session.flush()
            for j in range(1, posts + 1):
                db.session.add(Post(user_id=u.id, title=f"Post {j} by User {i}", body="Lorem ipsum"))
        db.session.commit()
        click.echo(f"Seeded {users} users with {posts} posts each")

    @app.cli.command("schema-sql")
    @click.option("--dialect", type=click.Choice(["postgresql", "sqlite", "mysql"], case_sensitive=False), help="Override SQL dialect for DDL output")
    @click.option("--output", type=click.Path(dir_okay=False, writable=True), help="Write SQL to file instead of stdout")
    def schema_sql(dialect: str | None, output: str | None):
        """Generate CREATE TABLE/INDEX SQL from SQLAlchemy models without executing."""
        engine = db.engine
        d = engine.dialect
        if dialect:
            from sqlalchemy.dialects import postgresql, sqlite, mysql

            d = {"postgresql": postgresql.dialect(), "sqlite": sqlite.dialect(), "mysql": mysql.dialect()}[dialect]

        stmts: list[str] = []
        md = db.metadata
        # Ensure deterministic order
        for table in md.sorted_tables:
            stmts.append(str(CreateTable(table).compile(dialect=d)).rstrip() + ";")
            for idx in sorted(table.indexes, key=lambda i: i.name or ""):
                stmts.append(str(CreateIndex(idx).compile(dialect=d)).rstrip() + ";")

        sql = "\n\n".join(stmts) + "\n"
        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(sql)
            click.echo(f"Wrote schema SQL to {output}")
        else:
            click.echo(sql)

    @app.cli.command("db-reset")
    @click.confirmation_option(prompt="This will DROP all tables and re-run migrations. Continue?")
    def db_reset():
        """Dangerous: Drop all tables and run migrations from scratch."""
        engine = db.engine
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("""
                    DO $$ DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                            EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                        END LOOP;
                    END $$;
                """))
                conn.commit()
            else:
                # SQLite or other: drop using metadata
                db.drop_all()
        
        db.create_all()
        click.echo("Database reset complete. All tables dropped and recreated.")
