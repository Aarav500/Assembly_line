import os
from dataclasses import dataclass


def _env(name: str, default=None, cast=str):
    val = os.getenv(name, default)
    if val is None:
        return None
    try:
        return cast(val)
    except Exception:
        return val


@dataclass
class Config:
    database_url: str | None
    host: str
    port: int
    user: str
    password: str | None
    dbname: str
    statement_timeout_ms: int
    min_slow_ms: int
    min_table_rows_for_index: int
    enable_pg_stat_statements_setup: bool

    @staticmethod
    def load() -> "Config":
        return Config(
            database_url=_env("DATABASE_URL", None, str),
            host=_env("DB_HOST", "127.0.0.1", str),
            port=_env("DB_PORT", 5432, int),
            user=_env("DB_USER", "postgres", str),
            password=_env("DB_PASSWORD", None, str),
            dbname=_env("DB_NAME", "postgres", str),
            statement_timeout_ms=_env("STATEMENT_TIMEOUT_MS", 10000, int),
            min_slow_ms=_env("MIN_SLOW_MS", 50, int),
            min_table_rows_for_index=_env("MIN_TABLE_ROWS_FOR_INDEX", 10000, int),
            enable_pg_stat_statements_setup=_env("ENABLE_PG_STAT_STATEMENTS_SETUP", "1", str) in ("1", "true", "TRUE", "yes", "on"),
        )

    def dsn(self) -> str:
        if self.database_url:
            return self.database_url
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"user={self.user}",
            f"dbname={self.dbname}",
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)

