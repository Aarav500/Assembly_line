import re
import sqlparse

# Basic static safety checks for SQL migrations. Not exhaustive.

def _strip_sql_comments(sql: str) -> str:
    # Remove SQL comments (both -- and /* */) to reduce false positives
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return ' ' * len(s)
        elif s.startswith('--'):
            return ' ' * len(s)
        return s
    pattern = re.compile(r"(--[^\n]*\n)|(/\*.*?\*/)", re.S)
    return re.sub(pattern, replacer, sql)


def _split_statements(sql: str):
    stmts = [s.strip() for s in sqlparse.split(sql) if s and s.strip()]
    return stmts


def analyze(sql: str, dialect: str = 'postgresql'):
    issues = []
    raw = sql or ""
    stripped = _strip_sql_comments(raw)
    lowered = stripped.lower()

    # Disallow DROP operations
    if re.search(r"\bdrop\s+(table|column|constraint|schema|database)\b", lowered):
        issues.append({
            "severity": "error",
            "code": "DROP_DETECTED",
            "message": "DROP operations detected. Use a two-step process (deprecate -> drop in separate window) and ensure backups."
        })

    # UPDATE/DELETE without WHERE
    for idx, stmt in enumerate(_split_statements(stripped)):
        s = stmt.strip().lower()
        if s.startswith("update") and " where " not in f" {s} ":
            issues.append({
                "severity": "error",
                "code": "UPDATE_NO_WHERE",
                "message": f"UPDATE statement #{idx+1} missing WHERE clause"
            })
        if s.startswith("delete") and " where " not in f" {s} ":
            issues.append({
                "severity": "error",
                "code": "DELETE_NO_WHERE",
                "message": f"DELETE statement #{idx+1} missing WHERE clause"
            })

    # CREATE INDEX without CONCURRENTLY (PostgreSQL)
    if dialect == 'postgresql':
        for idx, stmt in enumerate(_split_statements(stripped)):
            s = stmt.strip()
            if re.search(r"^\s*create\s+index\b", s, re.I) and not re.search(r"concurrently", s, re.I):
                issues.append({
                    "severity": "warning",
                    "code": "INDEX_NOT_CONCURRENTLY",
                    "message": f"Statement #{idx+1} creates index without CONCURRENTLY (may lock writes)"
                })

    # ALTER TABLE ADD COLUMN NOT NULL without DEFAULT (potential full table rewrite)
    for idx, stmt in enumerate(_split_statements(stripped)):
        s = stmt.strip().lower()
        if s.startswith("alter table") and " add column " in s and " not null" in s and " default " not in s:
            issues.append({
                "severity": "warning",
                "code": "ADD_NOT_NULL_NO_DEFAULT",
                "message": f"Statement #{idx+1} adds NOT NULL column without DEFAULT; may fail or lock. Consider backfill pattern."
            })

    # VACUUM FULL or CLUSTER can be dangerous in prod
    if re.search(r"\b(vacuum\s+full|cluster\b)", lowered):
        issues.append({
            "severity": "warning",
            "code": "HEAVY_MAINTENANCE",
            "message": "VACUUM FULL/CLUSTER detected; may require downtime"
        })

    # BEGIN/COMMIT included in migration (we manage transaction) - warn
    if re.search(r"\b(begin|commit|rollback)\b", lowered):
        issues.append({
            "severity": "warning",
            "code": "MANUAL_TXN",
            "message": "Explicit transaction control detected; the pipeline runs migrations in managed transactions"
        })

    # Multiple DDL mixed with DML - informational
    stmts = _split_statements(stripped)
    has_ddl = any(re.match(r"\s*(create|alter|drop|truncate)\b", s, re.I) for s in stmts)
    has_dml = any(re.match(r"\s*(insert|update|delete|merge)\b", s, re.I) for s in stmts)
    if has_ddl and has_dml:
        issues.append({
            "severity": "info",
            "code": "MIXED_DDL_DML",
            "message": "Migration mixes DDL and DML; consider separating for safer rollouts"
        })

    return issues

