from __future__ import annotations
import collections
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from config import Settings
from models import Function, ImportUsage, Project
from analysis.similarity import top_pairwise_similar


def find_similar_functions(db: Session, threshold: float | None = None, limit: int = 200) -> list[dict]:
    settings = Settings()
    thr = threshold if threshold is not None else settings.JACCARD_THRESHOLD

    funcs = db.query(Function).all()
    items = [(f.id, f.project_id, f.shingles()) for f in funcs]
    pairs = top_pairwise_similar(items, threshold=thr, limit=limit)

    # Build mapping for quick lookup
    by_id: Dict[int, Function] = {f.id: f for f in funcs}

    result: list[dict] = []
    for a_id, b_id, score in pairs:
        fa = by_id.get(a_id)
        fb = by_id.get(b_id)
        if not fa or not fb or fa.project_id == fb.project_id:
            continue
        result.append({
            "a": {
                "function_id": fa.id,
                "project_id": fa.project_id,
                "qualname": fa.qualname,
                "file": fa.file.rel_path if fa.file else None,
                "lines": [fa.start_line, fa.end_line],
            },
            "b": {
                "function_id": fb.id,
                "project_id": fb.project_id,
                "qualname": fb.qualname,
                "file": fb.file.rel_path if fb.file else None,
                "lines": [fb.start_line, fb.end_line],
            },
            "similarity": score,
        })
    return result


def group_duplicates(db: Session, threshold: float | None = None) -> list[list[int]]:
    settings = Settings()
    thr = threshold if threshold is not None else settings.JACCARD_THRESHOLD

    funcs = db.query(Function).all()
    items = [(f.id, f.project_id, f.shingles()) for f in funcs]
    pairs = top_pairwise_similar(items, threshold=thr, limit=50000)

    # Union-find for grouping
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a: int, b: int):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b, _ in pairs:
        union(a, b)

    groups: dict[int, list[int]] = collections.defaultdict(list)
    for f_id, _, _ in items:
        if f_id in parent:
            groups[find(f_id)].append(f_id)

    return [sorted(v) for v in groups.values() if len(v) > 1]


def summarize_groups(db: Session, groups: list[list[int]]) -> list[dict]:
    if not groups:
        return []
    funcs = db.query(Function).filter(Function.id.in_([fid for g in groups for fid in g])).all()
    by_id = {f.id: f for f in funcs}

    summaries: list[dict] = []
    for g in groups:
        projects = {by_id[fid].project_id for fid in g if fid in by_id}
        if len(projects) < 2:
            continue
        members = []
        for fid in g:
            f = by_id.get(fid)
            if not f:
                continue
            members.append({
                "function_id": f.id,
                "project_id": f.project_id,
                "qualname": f.qualname,
                "file": f.file.rel_path if f.file else None,
                "lines": [f.start_line, f.end_line],
            })
        summaries.append({
            "projects_involved": sorted(list(projects)),
            "size": len(members),
            "members": members,
        })
    # sort groups by size descending
    summaries.sort(key=lambda x: x["size"], reverse=True)
    return summaries


def popular_imports(db: Session, top_n: int = 15) -> list[dict]:
    rows = db.query(ImportUsage.module, ImportUsage.project_id).all()
    count_by_module = collections.Counter([r[0] for r in rows])
    projects_by_module: dict[str, set[int]] = collections.defaultdict(set)
    for module, pid in rows:
        projects_by_module[module].add(pid)
    items = []
    for module, count in count_by_module.most_common(top_n * 2):
        items.append({
            "module": module,
            "occurrences": count,
            "projects": sorted(list(projects_by_module[module])),
            "project_count": len(projects_by_module[module]),
        })
    # Prefer imports shared across multiple projects
    items.sort(key=lambda x: (x["project_count"], x["occurrences"]), reverse=True)
    return items[:top_n]


def build_reuse_suggestions(group_summaries: list[dict]) -> list[dict]:
    suggestions: list[dict] = []
    for group in group_summaries:
        # Suggest a shared utility when 2+ projects have similar function groups
        if group["size"] >= 2 and len(group["projects_involved"]) >= 2:
            example = group["members"][0]
            suggestions.append({
                "type": "shared_utility_candidate",
                "projects": group["projects_involved"],
                "example_function": example["qualname"],
                "files": list({m["file"] for m in group["members"] if m.get("file")}),
                "rationale": "Similar or duplicate functions detected across projects. Consider extracting to a shared module/API.",
            })
    return suggestions[:50]


def build_report(db: Session) -> dict:
    # Duplicates/groups
    groups = group_duplicates(db)
    summaries = summarize_groups(db, groups)

    # Imports
    imports = popular_imports(db)

    # Suggestions
    suggestions = build_reuse_suggestions(summaries)

    # Basic project listing
    projects = db.query(Project).all()
    project_map = {p.id: {"id": p.id, "name": p.name} for p in projects}

    return {
        "projects": list(project_map.values()),
        "duplicates": {
            "group_count": len(summaries),
            "groups": summaries,
        },
        "popular_imports": imports,
        "suggestions": suggestions,
    }

