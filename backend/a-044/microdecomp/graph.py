from typing import Dict
from .utils import safe_div


def summarize_graph(packages: Dict[str, Dict]) -> Dict:
    total_loc = sum(p.get("loc", 0) for p in packages.values())
    total_pkgs = len(packages)
    edges = 0
    for p, data in packages.items():
        edges += sum(data.get("dependencies_out", {}).values())
    avg_loc = safe_div(total_loc, total_pkgs)
    avg_instability = safe_div(sum(p.get("instability", 0.0) for p in packages.values()), total_pkgs)
    avg_cohesion = safe_div(sum(p.get("cohesion", 0.0) for p in packages.values()), total_pkgs)
    return {
        "total_loc": total_loc,
        "packages": total_pkgs,
        "edges": edges,
        "avg_loc_per_package": avg_loc,
        "avg_instability": avg_instability,
        "avg_cohesion": avg_cohesion,
    }

