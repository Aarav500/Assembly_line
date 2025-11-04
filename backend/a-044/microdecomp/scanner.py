import ast
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Set, Tuple, Optional

from .utils import iter_py_files, top_level_packages, normalize_module_path, first_package_from_module

@dataclass
class Endpoint:
    package: str
    module: str
    blueprint: Optional[str]
    route: str
    methods: List[str]

@dataclass
class Model:
    package: str
    module: str
    name: str

@dataclass
class ModuleInfo:
    id: str
    path: str
    package: str
    loc: int
    imports: Set[str]
    internal_imports: Set[str]
    endpoints: List[Endpoint]
    blueprints: List[str]
    models: List[Model]


def _count_loc(source: str) -> int:
    cnt = 0
    for line in source.splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        cnt += 1
    return cnt

class ImportVisitor(ast.NodeVisitor):
    def __init__(self, current_module: str, tlpkgs: Set[str]):
        self.current_module = current_module
        self.tlpkgs = tlpkgs
        self.imports: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.name.split('.')[0]
            if name in self.tlpkgs:
                self.imports.add(name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None:
            # relative import like from . import x
            base = self.current_module.rsplit('.', node.level)[0] if node.level else self.current_module
            top = base.split('.')[0] if base else ''
            if top in self.tlpkgs:
                self.imports.add(top)
            return
        mod = node.module
        top = mod.split('.')[0]
        if top in self.tlpkgs:
            self.imports.add(top)

class FlaskVisitor(ast.NodeVisitor):
    def __init__(self):
        self.blueprint_vars: Dict[str, Dict] = {}  # var -> {name, url_prefix}
        self.routes: List[Tuple[Optional[str], str, List[str]]] = []  # (blueprint_var or None, route, methods)

    def visit_Assign(self, node: ast.Assign):
        # bp = Blueprint('users', __name__, url_prefix='/users')
        try:
            if isinstance(node.value, ast.Call):
                func = node.value.func
                func_name = None
                if isinstance(func, ast.Name):
                    func_name = func.id
                elif isinstance(func, ast.Attribute):
                    func_name = func.attr
                if func_name == 'Blueprint':
                    bp_name = None
                    url_prefix = None
                    if node.value.args and isinstance(node.value.args[0], ast.Constant):
                        bp_name = str(node.value.args[0].value)
                    for kw in node.value.keywords:
                        if kw.arg == 'url_prefix' and isinstance(kw.value, ast.Constant):
                            url_prefix = str(kw.value.value)
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.blueprint_vars[target.id] = {"name": bp_name, "url_prefix": url_prefix}
        except Exception:
            pass
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._inspect_decorators(node.decorator_list)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._inspect_decorators(node.decorator_list)
        self.generic_visit(node)

    def _inspect_decorators(self, decorators):
        for d in decorators:
            try:
                if isinstance(d, ast.Call):
                    func = d.func
                else:
                    func = d
                bp_var = None
                is_route = False
                if isinstance(func, ast.Attribute) and func.attr == 'route':
                    is_route = True
                    if isinstance(func.value, ast.Name):
                        bp_var = func.value.id
                    elif isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name):
                        bp_var = func.value.value.id
                elif isinstance(func, ast.Name) and func.id == 'route':
                    # from flask import route (unlikely)
                    is_route = True
                if is_route:
                    route = None
                    methods: List[str] = []
                    if isinstance(d, ast.Call):
                        # args
                        if d.args and isinstance(d.args[0], ast.Constant):
                            route = str(d.args[0].value)
                        for kw in d.keywords:
                            if kw.arg == 'methods':
                                if isinstance(kw.value, (ast.List, ast.Tuple)):
                                    for el in kw.value.elts:
                                        if isinstance(el, ast.Constant):
                                            methods.append(str(el.value).upper())
                    self.routes.append((bp_var, route or "", methods or ["GET"]))
            except Exception:
                continue

class ModelVisitor(ast.NodeVisitor):
    def __init__(self):
        self.models: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        try:
            for base in node.bases:
                # db.Model, Model, Base, declarative_base() types
                if isinstance(base, ast.Attribute) and base.attr == 'Model':
                    self.models.append(node.name)
                    return
                if isinstance(base, ast.Name) and base.id in {"Model", "Base"}:
                    self.models.append(node.name)
                    return
        except Exception:
            pass
        self.generic_visit(node)


def parse_file(full_path: str, rel_path: str, tlpkgs: Set[str]) -> ModuleInfo:
    module_id = normalize_module_path(rel_path)
    pkg = first_package_from_module(module_id)
    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            src = f.read()
    except Exception:
        src = ''
    loc = _count_loc(src)
    try:
        tree = ast.parse(src)
    except Exception:
        tree = ast.parse("")
    iv = ImportVisitor(module_id, tlpkgs)
    iv.visit(tree)
    fv = FlaskVisitor()
    fv.visit(tree)
    mv = ModelVisitor()
    mv.visit(tree)

    endpoints: List[Endpoint] = []
    for bp_var, route, methods in fv.routes:
        bp_name = None
        if bp_var and bp_var in fv.blueprint_vars:
            bp_name = fv.blueprint_vars[bp_var]["name"] or bp_var
        endpoints.append(Endpoint(package=pkg, module=module_id, blueprint=bp_name, route=route, methods=methods))

    models: List[Model] = [Model(package=pkg, module=module_id, name=n) for n in mv.models]

    return ModuleInfo(
        id=module_id,
        path=rel_path,
        package=pkg,
        loc=loc,
        imports=set(iv.imports),
        internal_imports=set(iv.imports),
        endpoints=endpoints,
        blueprints=[v.get('name') or k for k, v in fv.blueprint_vars.items()],
        models=models,
    )


def scan_project(root: str, include_tests: bool = False) -> Dict:
    tlpkgs = top_level_packages(root)
    modules: Dict[str, ModuleInfo] = {}
    packages: Dict[str, Dict] = {}

    for full, rel in iter_py_files(root, include_tests=include_tests):
        mi = parse_file(full, rel, tlpkgs)
        modules[mi.id] = mi
        packages.setdefault(mi.package, {"modules": [], "loc": 0, "endpoints": [], "models": [], "blueprints": set()})
        packages[mi.package]["modules"].append(mi.id)
        packages[mi.package]["loc"] += mi.loc
        packages[mi.package]["endpoints"].extend([asdict(e) for e in mi.endpoints])
        packages[mi.package]["models"].extend([asdict(m) for m in mi.models])
        for bp in mi.blueprints:
            packages[mi.package]["blueprints"].add(bp)

    # build dependency edges at package level from module imports
    pkg_edges = {p: {"out": {}, "in": {}} for p in packages.keys()}
    for m in modules.values():
        for imp_top in m.internal_imports:
            if imp_top == m.package:
                continue
            pkg_edges[m.package]["out"][imp_top] = pkg_edges[m.package]["out"].get(imp_top, 0) + 1
            pkg_edges[imp_top]["in"][m.package] = pkg_edges[imp_top]["in"].get(m.package, 0) + 1

    # finalize packages
    for p, data in packages.items():
        data["blueprints"] = sorted(list(data["blueprints"]))
        out_deg = sum(pkg_edges[p]["out"].values())
        in_deg = sum(pkg_edges[p]["in"].values())
        data["dependencies_out"] = pkg_edges[p]["out"]
        data["dependencies_in"] = pkg_edges[p]["in"]
        data["afferent"] = in_deg
        data["efferent"] = out_deg
        total = in_deg + out_deg
        data["instability"] = (out_deg / total) if total else 0.0

    # compute cohesion: internal import ratio per package using module-level edges
    # approximation: for modules within same package, count imports to same package
    internal_refs = {p: 0 for p in packages.keys()}
    total_refs = {p: 0 for p in packages.keys()}
    for m in modules.values():
        for imp in m.internal_imports:
            total_refs[m.package] += 1
            if imp == m.package:
                internal_refs[m.package] += 1
    for p in packages.keys():
        data = packages[p]
        data["cohesion"] = (internal_refs[p] / total_refs[p]) if total_refs[p] else 0.0

    # detect cycles between packages using DFS
    cycles = _find_cycles(packages)

    return {
        "packages": packages,
        "modules": {k: asdict(v) for k, v in modules.items()},
        "top_level_packages": sorted(list(tlpkgs)),
        "cycles": cycles,
    }


def _find_cycles(packages: Dict[str, Dict]) -> List[List[str]]:
    graph = {p: list(packages[p].get("dependencies_out", {}).keys()) for p in packages.keys()}
    visited = set()
    stack = []
    onstack = set()
    cycles = []

    def dfs(u: str):
        visited.add(u)
        onstack.add(u)
        stack.append(u)
        for v in graph.get(u, []):
            if v not in visited:
                dfs(v)
            elif v in onstack:
                # found a cycle, extract path
                if v in stack:
                    idx = stack.index(v)
                    cyc = stack[idx:].copy()
                    if cyc and cyc not in cycles:
                        cycles.append(cyc)
        stack.pop()
        onstack.discard(u)

    for node in graph.keys():
        if node not in visited:
            dfs(node)
    return cycles

