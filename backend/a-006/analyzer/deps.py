import ast
import os
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from .utils import rel_module_name, iter_source_files

try:
    STDLIB_MODULES = set(sys.stdlib_module_names)  # Python 3.10+
except Exception:
    # Fallback minimal set
    STDLIB_MODULES = {
        "sys", "os", "re", "json", "math", "time", "datetime", "pathlib", "itertools", "functools", "collections",
        "typing", "subprocess", "threading", "asyncio", "unittest", "logging", "argparse", "shutil", "tempfile", "http",
    }


def parse_python_imports(code: str) -> List[str]:
    imports: List[str] = []
    try:
        tree = ast.parse(code)
    except Exception:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def analyze_dependencies(base_path: str) -> Dict:
    base_path = os.path.abspath(base_path)
    internal_index: Dict[str, str] = {}
    for f in iter_source_files(base_path):
        if f.endswith(".py"):
            mod = rel_module_name(base_path, f)
            internal_index[mod.split(".")[0]] = f  # register top-level package/module

    internal_nodes: Set[str] = set()
    edges: List[Dict[str, str]] = []

    external_counter: Dict[str, int] = defaultdict(int)

    for f in iter_source_files(base_path):
        if not f.endswith(".py"):
            continue
        rel_mod = rel_module_name(base_path, f)
        internal_nodes.add(rel_mod)
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                code = fh.read()
        except Exception:
            code = ""
        imports = parse_python_imports(code)
        for pkg in imports:
            if not pkg:
                continue
            if pkg in internal_index:
                edges.append({"from": rel_mod, "to": pkg})
            else:
                # classify as stdlib or external
                if pkg not in STDLIB_MODULES:
                    external_counter[pkg] += 1

    top_external = sorted(external_counter.items(), key=lambda kv: kv[1], reverse=True)

    return {
        "internal_nodes": sorted(list(internal_nodes)),
        "internal_edges": edges,
        "external_packages": external_counter,
        "top_external_packages": [{"package": k, "count": v} for k, v in top_external[:15]],
    }

