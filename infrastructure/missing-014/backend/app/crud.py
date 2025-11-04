from typing import Dict, Iterable, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import Translation


def get_translations(db: Session, language: str, namespace: str) -> List[Translation]:
    stmt = select(Translation).where(
        Translation.language == language, Translation.namespace == namespace
    )
    return list(db.execute(stmt).scalars())


def get_translations_dict(db: Session, language: str, namespace: str) -> Dict[str, str]:
    rows = get_translations(db, language, namespace)
    return {row.key: row.value for row in rows}


def upsert_translation(db: Session, language: str, namespace: str, key: str, value: str) -> Translation:
    # Try find existing
    row = db.execute(
        select(Translation).where(
            Translation.language == language, Translation.namespace == namespace, Translation.key == key
        )
    ).scalar_one_or_none()
    if row is None:
        row = Translation(language=language, namespace=namespace, key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    db.refresh(row)
    return row


def upsert_many(db: Session, items: Iterable[Tuple[str, str, str, str]]) -> List[Translation]:
    results: List[Translation] = []
    for language, namespace, key, value in items:
        results.append(upsert_translation(db, language, namespace, key, value))
    return results

