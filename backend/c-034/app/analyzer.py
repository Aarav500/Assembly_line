import importlib
import json
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql.schema import Table, Column


@dataclass
class Suggestion:
    table: str
    action: str  # create_table | drop_table | add_column | drop_column | alter_column_type | alter_column_nullable | add_default | drop_default
    column: Optional[str]
    safety: str  # safe | caution | dangerous
    rationale: str
    sql: Optional[str] = None
    alembic_ops: Optional[List[str]] = None
    recommended_steps: Optional[List[str]] = None


@dataclass
class TableReport:
    name: str
    status: str  # ok | missing_in_db | extra_in_db | diff
    suggestions: List[Suggestion]
    row_count: Optional[int] = None


@dataclass
class AnalysisResult:
    tables: List[TableReport]
    summary: Dict[str, Any]
    engine_dialect: str


def load_models_metadata(models_module_path: str) -> MetaData:
    mod = importlib.import_module(models_module_path)
    # Heuristic: look for attribute named Base with metadata
    base = getattr(mod, "Base", None)
    if base is not None and hasattr(base, "metadata"):
        return base.metadata

    # Fallback: collect first MetaData found
    for v in mod.__dict__.values():
        if isinstance(v, MetaData):
            return v
    raise RuntimeError(f"Could not find SQLAlchemy Base.metadata in module {models_module_path}")


def reflect_db_metadata(engine: Engine) -> MetaData:
    md = MetaData()
    md.reflect(bind=engine)
    return md


def type_signature(col: Column, engine: Engine) -> str:
    # Compile the type against engine dialect for comparable signature
    try:
        return col.type.compile(dialect=engine.dialect)
    except Exception:
        # Fallback to string repr
        return str(col.type)


def parse_type_signature(sig: str) -> Tuple[str, Optional[int]]:
    # Extract type family and optional length, e.g., VARCHAR(255) -> (varchar, 255)
    s = sig.lower()
    m = re.match(r"([a-z_]+)\s*\(\s*(\d+)\s*\)", s)
    if m:
        return m.group(1), int(m.group(2))
    # handle types like character varying(255)
    m = re.match(r"([a-z_ ]+)\s*\(\s*(\d+)\s*\)", s)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return s.strip(), None


def is_widening_type_change(db_sig: str, model_sig: str) -> bool:
    db_family, db_len = parse_type_signature(db_sig)
    model_family, model_len = parse_type_signature(model_sig)
    if db_family == model_family and db_len is not None and model_len is not None:
        return model_len > db_len
    # Integer to BigInteger as widening
    if db_family in ("integer", "int", "smallint") and model_family in ("bigint", "big integer"):
        return True
    return False


def is_shrinking_type_change(db_sig: str, model_sig: str) -> bool:
    db_family, db_len = parse_type_signature(db_sig)
    model_family, model_len = parse_type_signature(model_sig)
    if db_family == model_family and db_len is not None and model_len is not None:
        return model_len < db_len
    # BigInteger to Integer as shrinking
    if db_family in ("bigint", "big integer") and model_family in ("integer", "int", "smallint"):
        return True
    return False


def estimate_row_counts(engine: Engine, tables: List[str], mode: str = "none", max_tables: int = 10) -> Dict[str, Optional[int]]:
    counts: Dict[str, Optional[int]] = {t: None for t in tables}
    if mode != "exact":
        return counts
    try:
        with engine.connect() as conn:
            for i, t in enumerate(tables):
                if i >= max_tables:
                    break
                try:
                    res = conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                    counts[t] = int(list(res)[0][0])
                except Exception:
                    counts[t] = None
    except Exception:
        pass
    return counts


def make_sql_add_column(table: str, col: Column, engine: Engine) -> str:
    sig = type_signature(col, engine)
    parts = [f'ALTER TABLE {table} ADD COLUMN {col.name} {sig}']
    if getattr(col, 'nullable', True) is False:
        parts.append('NOT NULL')
    # server_default may be a SQL text; best effort string
    if getattr(col, 'server_default', None) is not None:
        parts.append(f"DEFAULT {col.server_default.arg.text if hasattr(col.server_default, 'arg') else col.server_default}")
    return ' '.join(parts) + ';'


def make_sql_alter_type(table: str, col_name: str, new_sig: str, engine: Engine) -> str:
    dialect_name = engine.dialect.name
    if dialect_name == 'postgresql':
        return f'ALTER TABLE {table} ALTER COLUMN {col_name} TYPE {new_sig};'
    # Generic dialect; many DBs: ALTER TABLE ALTER COLUMN TYPE is not standard; fallback
    return f'-- Review required: type change may be dialect-specific\nALTER TABLE {table} ALTER COLUMN {col_name} TYPE {new_sig};'


def make_sql_alter_nullable(table: str, col_name: str, nullable: bool, engine: Engine) -> str:
    dialect_name = engine.dialect.name
    if dialect_name == 'postgresql':
        return f"ALTER TABLE {table} ALTER COLUMN {col_name} {'DROP' if nullable else 'SET'} NOT NULL;"
    return f"-- Review required: nullability change may be dialect-specific\nALTER TABLE {table} ALTER COLUMN {col_name} {'DROP' if nullable else 'SET'} NOT NULL;"


def make_sql_create_table(table: Table, engine: Engine) -> str:
    try:
        return str(CreateTable(table).compile(dialect=engine.dialect)) + ';'
    except Exception:
        return f"-- Failed to auto-generate CREATE TABLE for {table.name}. Fill in manually."


def compare_schemas(models_md: MetaData, db_md: MetaData, engine: Engine, include_sql: bool = True, include_alembic_ops: bool = True) -> AnalysisResult:
    model_tables = {t.name: t for t in models_md.sorted_tables}
    db_tables = {t.name: t for t in db_md.sorted_tables}

    all_table_names = sorted(set(model_tables.keys()) | set(db_tables.keys()))
    counts = estimate_row_counts(engine, all_table_names, mode="none")

    reports: List[TableReport] = []
    safe_count = caution_count = dangerous_count = 0

    for tname in all_table_names:
        suggestions: List[Suggestion] = []
        status = 'ok'
        model_t = model_tables.get(tname)
        db_t = db_tables.get(tname)

        if model_t and not db_t:
            status = 'missing_in_db'
            s = Suggestion(
                table=tname,
                action='create_table',
                column=None,
                safety='safe',
                rationale='Model defines table that does not exist in DB; creating a new table is non-destructive.',
                sql=make_sql_create_table(model_t, engine) if include_sql else None,
                alembic_ops=[f"op.create_table('{tname}', ...)" ] if include_alembic_ops else None,
            )
            safe_count += 1
            suggestions.append(s)
        elif db_t and not model_t:
            status = 'extra_in_db'
            s = Suggestion(
                table=tname,
                action='drop_table',
                column=None,
                safety='dangerous',
                rationale='DB has a table that models do not reference; dropping can cause data loss. Consider deprecating or archiving first.',
                sql=f'DROP TABLE {tname};' if include_sql else None,
                alembic_ops=[f"op.drop_table('{tname}')"] if include_alembic_ops else None,
                recommended_steps=[
                    'Confirm table is unused and not referenced by other services',
                    'Take a backup or snapshot before dropping',
                    'Optionally rename table to *_deprecated for a release before dropping',
                ],
            )
            dangerous_count += 1
            suggestions.append(s)
        else:
            # Both exist: compare columns
            col_names_model = {c.name: c for c in model_t.columns}
            col_names_db = {c.name: c for c in db_t.columns}
            table_diff = False

            # Missing columns in DB
            for cname, mcol in col_names_model.items():
                if cname not in col_names_db:
                    table_diff = True
                    nullable = getattr(mcol, 'nullable', True)
                    has_default = getattr(mcol, 'server_default', None) is not None
                    safety = 'safe' if (nullable or has_default) else 'caution'
                    rationale = 'Adding a column is generally safe; however NOT NULL without a default requires careful backfill.'
                    sql = make_sql_add_column(tname, mcol, engine) if include_sql else None
                    alembic_ops = [f"op.add_column('{tname}', sa.Column('{cname}', sa.{type_signature(mcol, engine)}, nullable={'False' if not nullable else 'True'}))"] if include_alembic_ops else None
                    recommended_steps = None
                    if safety == 'caution':
                        recommended_steps = [
                            'Add the column as NULLABLE with default if possible',
                            'Backfill data in batches',
                            'Add NOT NULL constraint after backfill completes',
                        ]
                    suggestions.append(Suggestion(
                        table=tname,
                        action='add_column',
                        column=cname,
                        safety=safety,
                        rationale=rationale,
                        sql=sql,
                        alembic_ops=alembic_ops,
                        recommended_steps=recommended_steps,
                    ))
                    if safety == 'safe':
                        safe_count += 1
                    else:
                        caution_count += 1

            # Extra columns in DB
            for cname, dcol in col_names_db.items():
                if cname not in col_names_model:
                    table_diff = True
                    s = Suggestion(
                        table=tname,
                        action='drop_column',
                        column=cname,
                        safety='dangerous',
                        rationale='Dropping a column removes data. Consider deprecating, archiving, or leaving as-is.',
                        sql=f'ALTER TABLE {tname} DROP COLUMN {cname};' if include_sql else None,
                        alembic_ops=[f"op.drop_column('{tname}', '{cname}')"] if include_alembic_ops else None,
                        recommended_steps=[
                            'Verify column is truly unused',
                            'Take a backup or export of data',
                            'Consider soft delete: keep in place for a release before dropping',
                        ],
                    )
                    suggestions.append(s)
                    dangerous_count += 1

            # Compare shared columns
            for cname, mcol in col_names_model.items():
                if cname in col_names_db:
                    dcol = col_names_db[cname]
                    m_sig = type_signature(mcol, engine)
                    d_sig = type_signature(dcol, engine)
                    # Type difference
                    if m_sig.lower() != d_sig.lower():
                        table_diff = True
                        if is_widening_type_change(d_sig, m_sig):
                            safety = 'caution'
                            rationale = 'Widening type change is generally safe but may lock the table; schedule during low traffic.'
                        elif is_shrinking_type_change(d_sig, m_sig):
                            safety = 'dangerous'
                            rationale = 'Shrinking type can truncate or fail on existing data; requires audit and backfill.'
                        else:
                            safety = 'caution'
                            rationale = 'Type change may be safe or risky depending on data; review and test carefully.'
                        sql = make_sql_alter_type(tname, cname, m_sig, engine) if include_sql else None
                        rec_steps = [
                            'Assess existing data compatibility',
                            'Run in staging with production-like data',
                            'Consider adding a new column, backfilling, then swapping names for zero-downtime',
                        ]
                        suggestions.append(Suggestion(
                            table=tname,
                            action='alter_column_type',
                            column=cname,
                            safety=safety,
                            rationale=rationale,
                            sql=sql,
                            alembic_ops=[f"op.alter_column('{tname}', '{cname}', type_=sa.{m_sig})"] if include_alembic_ops else None,
                            recommended_steps=rec_steps,
                        ))
                        if safety == 'dangerous':
                            dangerous_count += 1
                        else:
                            caution_count += 1

                    # Nullability difference
                    m_null = getattr(mcol, 'nullable', True)
                    d_null = getattr(dcol, 'nullable', True)
                    if bool(m_null) != bool(d_null):
                        table_diff = True
                        if not m_null and d_null:
                            safety = 'caution'
                            rationale = 'Adding NOT NULL constraint requires existing rows to be populated.'
                        else:
                            safety = 'safe'
                            rationale = 'Making a column NULLABLE is non-destructive.'
                        sql = make_sql_alter_nullable(tname, cname, m_null, engine) if include_sql else None
                        suggestions.append(Suggestion(
                            table=tname,
                            action='alter_column_nullable',
                            column=cname,
                            safety=safety,
                            rationale=rationale,
                            sql=sql,
                            alembic_ops=[f"op.alter_column('{tname}', '{cname}', nullable={m_null})"] if include_alembic_ops else None,
                            recommended_steps=([
                                'Backfill NULLs for existing rows',
                                'Add application-level writes to ensure non-null going forward',
                            ] if safety == 'caution' else None),
                        ))
                        if safety == 'safe':
                            safe_count += 1
                        else:
                            caution_count += 1

            if table_diff and status == 'ok':
                status = 'diff'

        reports.append(TableReport(
            name=tname,
            status=status,
            suggestions=suggestions,
            row_count=counts.get(tname)
        ))

    result = AnalysisResult(
        tables=reports,
        summary={
            'safe': safe_count,
            'caution': caution_count,
            'dangerous': dangerous_count,
            'tables_analyzed': len(all_table_names),
        },
        engine_dialect=engine.dialect.name,
    )
    return result


def analyze(database_url: str, models_module: str, include_sql: bool = True, include_alembic_ops: bool = True) -> Dict[str, Any]:
    engine = create_engine(database_url)
    models_md = load_models_metadata(models_module)
    db_md = reflect_db_metadata(engine)
    result = compare_schemas(models_md, db_md, engine, include_sql=include_sql, include_alembic_ops=include_alembic_ops)
    # Convert dataclasses to plain dicts
    def ser_sug(s: Suggestion) -> Dict[str, Any]:
        d = asdict(s)
        return d

    payload = {
        'engine_dialect': result.engine_dialect,
        'summary': result.summary,
        'tables': [
            {
                'name': tr.name,
                'status': tr.status,
                'row_count': tr.row_count,
                'suggestions': [ser_sug(s) for s in tr.suggestions]
            } for tr in result.tables
        ]
    }
    return payload

