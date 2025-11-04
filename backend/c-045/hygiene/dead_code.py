import ast
import os
from typing import Dict, List, Set, Any

IGNORED_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "node_modules", ".mypy_cache", ".pytest_cache"}


def discover_python_files(root: str, exclude: List[str] = None) -> List[str]:
    exclude = set(exclude or [])
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and d not in exclude]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(dirpath, fname))
    return files


class RefCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.defined_funcs: Set[str] = set()
        self.defined_classes: Set[str] = set()
        self.used_names: Set[str] = set()
        self.route_decorated_funcs: Set[str] = set()
        self.exported_names: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.defined_funcs.add(node.name)
        # detect Flask route decorators
        for deco in node.decorator_list:
            if isinstance(deco, ast.Call):
                target = deco.func
            else:
                target = deco
            if isinstance(target, ast.Attribute) and target.attr in {"route", "get", "post", "put", "delete", "patch"}:
                self.route_decorated_funcs.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.defined_funcs.add(node.name)
        for deco in node.decorator_list:
            if isinstance(deco, ast.Call):
                target = deco.func
            else:
                target = deco
            if isinstance(target, ast.Attribute) and target.attr in {"route", "get", "post", "put", "delete", "patch"}:
                self.route_decorated_funcs.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.defined_classes.add(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        # detect __all__ = ["name", ...]
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                names = set()
                if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.add(elt.value)
                self.exported_names |= names
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        # Count every Name usage. We'll subtract definitions via sets above.
        self.used_names.add(node.id)
        self.generic_visit(node)


def find_dead_code(path: str, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    options = options or {}
    exclude = options.get("exclude", [])
    ignore_private = bool(options.get("ignore_private", True))
    files = discover_python_files(path, exclude=exclude)

    errors: List[Dict[str, str]] = []
    module_reports: List[Dict[str, Any]] = []

    global_used: Set[str] = set()
    global_defined_funcs: Dict[str, List[str]] = {}
    global_defined_classes: Dict[str, List[str]] = {}
    routed_funcs_global: Set[str] = set()
    exported_global: Set[str] = set()

    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=file)
        except Exception as e:
            errors.append({"file": file, "error": str(e)})
            continue

        rc = RefCollector()
        rc.visit(tree)

        global_used |= rc.used_names
        for name in rc.defined_funcs:
            global_defined_funcs.setdefault(name, []).append(file)
        for name in rc.defined_classes:
            global_defined_classes.setdefault(name, []).append(file)
        routed_funcs_global |= rc.route_decorated_funcs
        exported_global |= rc.exported_names

    # Compute dead sets
    def is_candidate(name: str) -> bool:
        if ignore_private and name.startswith("_"):
            return False
        if name in {"__init__", "__main__"}:
            return False
        return True

    dead_funcs = []
    for name, files_defined in global_defined_funcs.items():
        if not is_candidate(name):
            continue
        if name in global_used:
            continue
        if name in routed_funcs_global:
            continue
        if name in exported_global:
            continue
        for file in files_defined:
            dead_funcs.append({"name": name, "file": file, "kind": "function"})

    dead_classes = []
    for name, files_defined in global_defined_classes.items():
        if not is_candidate(name):
            continue
        if name in global_used:
            continue
        if name in exported_global:
            continue
        for file in files_defined:
            dead_classes.append({"name": name, "file": file, "kind": "class"})

    # Group by file for easier consumption
    by_file: Dict[str, Dict[str, Any]] = {}
    for item in dead_funcs + dead_classes:
        f = item["file"]
        by_file.setdefault(f, {"file": f, "dead": []})["dead"].append(item)

    module_reports = list(by_file.values())
    module_reports.sort(key=lambda m: m["file"])
    for m in module_reports:
        m["dead"].sort(key=lambda x: (x["kind"], x["name"]))

    return {
        "summary": {
            "files_scanned": len(files),
            "dead_items": len(dead_funcs) + len(dead_classes),
            "errors": len(errors),
        },
        "dead_by_file": module_reports,
        "dead_items": sorted(dead_funcs + dead_classes, key=lambda x: (x["file"], x["kind"], x["name"])) ,
        "errors": errors,
        "notes": [
            "Heuristic analysis: may produce false positives/negatives, especially for dynamic attribute access or imports.",
            "Functions decorated as Flask routes are treated as used.",
            "Names included in __all__ are treated as used.",
        ],
    }

