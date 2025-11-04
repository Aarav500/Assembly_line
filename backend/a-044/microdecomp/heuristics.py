from typing import Dict, List, Any, Tuple
from datetime import datetime
from .graph import summarize_graph
from .utils import safe_div

DEFAULT_THRESHOLDS = {
    "min_pkg_loc": 300,
    "max_pkg_loc": 10000,
    "min_cohesion": 0.55,
    "max_instability": 0.7,
    "max_out_deps": 6,
}


def suggest_decomposition(project_name: str, scan: Dict, git: Dict, thresholds: Dict = None) -> Dict:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    packages = scan["packages"]
    cycles = scan.get("cycles") or []
    graph_summary = summarize_graph(packages)

    candidates: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if cycles:
        warnings.append(f"Detected {len(cycles)} cyclic dependency cycle(s) among packages: {cycles}")

    # compute candidate score per package
    for pkg, data in packages.items():
        loc = data.get("loc", 0)
        cohesion = data.get("cohesion", 0.0)
        instab = data.get("instability", 0.0)
        out_deps = len(data.get("dependencies_out", {}))
        in_deps = len(data.get("dependencies_in", {}))
        blueprints = data.get("blueprints", [])
        endpoints = data.get("endpoints", [])
        models = data.get("models", [])

        reasons: List[str] = []
        score = 0.0

        if loc >= thresholds["min_pkg_loc"]:
            score += 1.0; reasons.append(f"Sufficient size: LOC={loc}")
        else:
            reasons.append(f"Small size: LOC={loc} (< {thresholds['min_pkg_loc']})")

        if loc <= thresholds["max_pkg_loc"]:
            score += 0.5
        else:
            reasons.append(f"Very large size: LOC={loc} (> {thresholds['max_pkg_loc']}) - consider split into sub-services")

        if cohesion >= thresholds["min_cohesion"]:
            score += 1.0; reasons.append(f"High internal cohesion={cohesion:.2f}")
        else:
            reasons.append(f"Low cohesion={cohesion:.2f}")

        if instab <= thresholds["max_instability"]:
            score += 0.5; reasons.append(f"Acceptable instability={instab:.2f}")
        else:
            reasons.append(f"High instability={instab:.2f} (many outbound deps)")

        if out_deps <= thresholds["max_out_deps"]:
            score += 0.5; reasons.append(f"Limited outbound deps={out_deps}")
        else:
            reasons.append(f"Many outbound deps={out_deps}")

        if blueprints or endpoints:
            score += 0.5; reasons.append(f"Contains API surface (blueprints={len(blueprints)}, endpoints={len(endpoints)})")

        if models:
            score += 0.5; reasons.append(f"Owns data models={len(models)}")

        # Adjust score if part of cycles
        in_cycle = any(pkg in cyc for cyc in cycles)
        if in_cycle:
            score -= 0.3
            reasons.append("Participates in dependency cycle; extraction will need detangling")

        # Git metrics insight
        change_pressure = _estimate_change_pressure(pkg, git)
        if change_pressure:
            score += 0.2; reasons.append(f"Active change frequency≈{change_pressure}")

        candidate = {
            "name": pkg,
            "score": round(score, 2),
            "metrics": {
                "loc": loc,
                "cohesion": round(cohesion, 3),
                "instability": round(instab, 3),
                "inbound_packages": in_deps,
                "outbound_packages": out_deps,
            },
            "blueprints": blueprints,
            "endpoints": endpoints,
            "models": models,
            "dependencies_out": data.get("dependencies_out", {}),
            "dependencies_in": data.get("dependencies_in", {}),
            "reasons": reasons,
        }
        candidates.append(candidate)

    # rank candidates highest score first, then lowest outbound deps, then highest cohesion
    candidates.sort(key=lambda c: (-c["score"], c["metrics"]["outbound_packages"], -c["metrics"]["cohesion"]))

    # Propose extraction order: prefer low outbound and not in cycles
    extraction_order = sorted(
        candidates,
        key=lambda c: (
            c["name"] in {pkg for cyc in cycles for pkg in cyc},
            c["metrics"]["outbound_packages"],
            -c["metrics"]["cohesion"],
        ),
    )

    plan = _build_plan(project_name, extraction_order, packages, cycles)

    return {
        "project": project_name,
        "summary": graph_summary,
        "candidates": candidates,
        "plan": plan,
        "cycles": cycles,
        "warnings": warnings,
    }


def _estimate_change_pressure(pkg: str, git: Dict) -> int:
    if not git or not git.get("available"):
        return 0
    # sum changes for files under this package
    fc = git.get("file_changes", {})
    total = 0
    for path, cnt in fc.items():
        # crude: check first segment of path matches pkg
        seg = path.split("/")[0]
        if seg == pkg:
            total += int(cnt)
    return total


def _build_plan(project_name: str, order: List[Dict], packages: Dict[str, Dict], cycles: List[List[str]]) -> Dict:
    steps_global: List[Dict[str, Any]] = []

    if cycles:
        steps_global.append({
            "title": "Break cyclic dependencies",
            "kind": "refactor",
            "details": {
                "cycles": cycles,
                "actions": [
                    "Introduce interfaces or domain events to invert dependencies",
                    "Extract shared DTOs/contracts to anti-corruption layer",
                    "Minimize cross-package imports by moving utilities to shared lib",
                ],
            },
        })

    steps_global.append({
        "title": "Identify and extract shared libraries",
        "kind": "preparation",
        "details": {
            "criteria": [
                "Pure utilities with no domain logic",
                "Cross-cutting concerns: auth, logging, validation",
            ],
            "output": "internal shared wheel or package",
        },
    })

    phases: List[Dict[str, Any]] = []

    # Phase 1: carve small, cohesive packages with minimal outbound deps
    batch1 = [c for c in order if c["metrics"]["outbound_packages"] <= 2][:3]
    if batch1:
        phases.append(_phase_from_batch(1, "Extract low-dependency services first", batch1, packages))

    # Phase 2: extract medium dependency services
    batch2 = [c for c in order if 3 <= c["metrics"]["outbound_packages"] <= 5][:5]
    if batch2:
        phases.append(_phase_from_batch(2, "Extract medium dependency services", batch2, packages))

    # Phase 3: high-dependency or cycle-involved services last
    batch3 = [c for c in order if c not in batch1 and c not in batch2]
    if batch3:
        phases.append(_phase_from_batch(3, "Extract complex/high-dependency services", batch3, packages))

    return {
        "global_preparation": steps_global,
        "phases": phases,
    }


def _phase_from_batch(index: int, title: str, batch: List[Dict], packages: Dict[str, Dict]) -> Dict:
    steps: List[Dict[str, Any]] = []
    for cand in batch:
        name = cand["name"]
        pkg = packages.get(name, {})
        endpoints = cand.get("endpoints", [])
        models = cand.get("models", [])
        deps_out = cand.get("dependencies_out", {})
        deps_in = cand.get("dependencies_in", {})

        step = {
            "service": name,
            "rationale": cand.get("reasons", [])[:5],
            "tasks": [
                {"title": "Create service skeleton", "items": [
                    f"New Flask app or Blueprint for {name}",
                    "Define WSGI entrypoint and containerization (Dockerfile)",
                    "Setup CI pipeline",
                ]},
                {"title": "Expose API endpoints", "items": _format_endpoints(endpoints)},
                {"title": "Define data ownership", "items": [
                    f"Move ORM models: {', '.join(sorted(set(m['name'] for m in models)))}" if models else "No ORM models detected",
                    "Establish separate database schema and migrations",
                ]},
                {"title": "Design service contracts", "items": _contract_suggestions(name, deps_out, deps_in)},
                {"title": "Implement strangler pattern", "items": [
                    "Route traffic to the new service behind a gateway",
                    "Add fallback to monolith until parity",
                    "Gradually deprecate monolith code paths",
                ]},
                {"title": "Observability & SLOs", "items": [
                    "Add structured logging, tracing, and metrics",
                    "Define health checks and readiness probes",
                ]},
            ],
        }
        steps.append(step)
    return {
        "index": index,
        "title": title,
        "services": [c["name"] for c in batch],
        "steps": steps,
    }


def _format_endpoints(endpoints: List[Dict]) -> List[str]:
    if not endpoints:
        return ["No Flask routes detected; expose minimal API as needed"]
    items = []
    for ep in endpoints:
        bp = ep.get("blueprint") or "app"
        route = ep.get("route") or "/"
        methods = ",".join(ep.get("methods") or ["GET"])
        items.append(f"{bp} {route} [{methods}]")
    return items


def _contract_suggestions(name: str, deps_out: Dict[str, int], deps_in: Dict[str, int]) -> List[str]:
    items: List[str] = []
    if deps_out:
        top = sorted(deps_out.items(), key=lambda kv: -kv[1])[:5]
        for dep, weight in top:
            items.append(f"Outbound to {dep} ({weight} refs): define REST client or async events")
    if deps_in:
        top = sorted(deps_in.items(), key=lambda kv: -kv[1])[:5]
        for dep, weight in top:
            items.append(f"Inbound from {dep} ({weight} refs): provide stable API and versioning")
    if not items:
        items.append("No strong dependencies detected; keep API lean")
    return items

