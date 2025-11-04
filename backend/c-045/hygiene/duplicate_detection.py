import ast
import hashlib
import os
from typing import Dict, List, Tuple, Any

IGNORED_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "node_modules", ".mypy_cache", ".pytest_cache"}


class NameNormalizer(ast.NodeTransformer):
    """
    Normalizes identifiers and constants to reduce spurious differences when comparing code bodies.
    - Variable, function, class names replaced with generic tokens
    - Argument names normalized
    - Constants replaced by their type/category
    - Removes docstrings from function/class bodies
    """

    def __init__(self) -> None:
        super().__init__()
        self._name_map: Dict[str, str] = {}
        self._counter = 0

    def _get_placeholder(self, original: str) -> str:
        if original not in self._name_map:
            self._counter += 1
            self._name_map[original] = f"VAR{self._counter}"
        return self._name_map[original]

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        node.name = "FUNC"
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args = self.visit(node.args)
        node.body = self._strip_docstring(node.body)
        node.body = [self.visit(n) for n in node.body]
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        node.name = "AFUNC"
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args = self.visit(node.args)
        node.body = self._strip_docstring(node.body)
        node.body = [self.visit(n) for n in node.body]
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        node.name = "CLASS"
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.bases = [self.visit(b) for b in node.bases]
        node.keywords = [self.visit(k) for k in node.keywords]
        node.body = self._strip_docstring(node.body)
        node.body = [self.visit(n) for n in node.body]
        return node

    def visit_arg(self, node: ast.arg) -> Any:
        node.arg = "ARG"
        if node.annotation:
            node.annotation = self.visit(node.annotation)
        return node

    def visit_Name(self, node: ast.Name) -> Any:
        # Preserve special names commonly used in Python
        if node.id in {"True", "False", "None"}:
            return node
        node.id = self._get_placeholder(node.id)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        node.value = self.visit(node.value)
        node.attr = "ATTR"
        return node

    def visit_Constant(self, node: ast.Constant) -> Any:
        val = node.value
        if isinstance(val, str):
            return ast.copy_location(ast.Constant(value="STR"), node)
        if isinstance(val, (int, float, complex)):
            return ast.copy_location(ast.Constant(value=0), node)
        if isinstance(val, bytes):
            return ast.copy_location(ast.Constant(value=b"B"), node)
        if isinstance(val, bool):
            return ast.copy_location(ast.Constant(value=True), node)
        if val is None:
            return ast.copy_location(ast.Constant(value=None), node)
        return node

    def _strip_docstring(self, body: List[ast.stmt]) -> List[ast.stmt]:
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            return body[1:]
        return body


def discover_python_files(root: str, exclude: List[str] = None) -> List[str]:
    exclude = set(exclude or [])
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and d not in exclude]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(dirpath, fname))
    return files


def _hash_node(node: ast.AST) -> str:
    normalizer = NameNormalizer()
    normalized = normalizer.visit(ast.fix_missing_locations(node))
    dumped = ast.dump(normalized, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def _collect_units(tree: ast.AST, filename: str) -> List[Tuple[str, str, int, str]]:
    """
    Returns list of (unit_type, name, lineno, digest)
    unit_type in {"function", "async_function", "class"}
    """
    results: List[Tuple[str, str, int, str]] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            try:
                digest = _hash_node(node)
            except Exception:
                digest = ""
            results.append(("function", node.name, getattr(node, "lineno", -1), digest))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            try:
                digest = _hash_node(node)
            except Exception:
                digest = ""
            results.append(("async_function", node.name, getattr(node, "lineno", -1), digest))
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            try:
                digest = _hash_node(node)
            except Exception:
                digest = ""
            results.append(("class", node.name, getattr(node, "lineno", -1), digest))
            self.generic_visit(node)

    Visitor().visit(tree)
    # attach filename afterwards in outer loop
    return results


def find_duplicates(path: str, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    options = options or {}
    exclude = options.get("exclude", [])
    files = discover_python_files(path, exclude=exclude)

    hash_map: Dict[str, List[Dict[str, Any]]] = {}
    errors: List[Dict[str, Any]] = []

    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=file)
        except Exception as e:
            errors.append({"file": file, "error": str(e)})
            continue

        for unit_type, name, lineno, digest in _collect_units(tree, file):
            if not digest:
                continue
            entry = {
                "file": file,
                "name": name,
                "lineno": lineno,
                "type": unit_type,
            }
            hash_map.setdefault(digest, []).append(entry)

    duplicates: List[Dict[str, Any]] = []
    for digest, occurrences in hash_map.items():
        if len(occurrences) > 1:
            duplicates.append({
                "hash": digest,
                "count": len(occurrences),
                "occurrences": sorted(occurrences, key=lambda o: (o["file"], o["lineno"]))
            })

    return {
        "summary": {
            "files_scanned": len(files),
            "duplicate_groups": len(duplicates),
            "errors": len(errors),
        },
        "duplicates": sorted(duplicates, key=lambda d: (-d["count"], d["hash"])),
        "errors": errors,
    }

