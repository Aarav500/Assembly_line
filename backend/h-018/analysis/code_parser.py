import ast
import hashlib
import json
import os
from typing import Iterator, Tuple

from sqlalchemy.orm import Session
from config import Settings
from models import Project, CodeFile, Function, ImportUsage


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def iter_py_files(root: str) -> Iterator[Tuple[str, str]]:
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith('.py'):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                yield rel, full


def normalize_identifier(name: str) -> str:
    # Simple normalization for names
    if not name:
        return "_"
    if name.startswith('__') and name.endswith('__'):
        return name  # magic methods preserved
    return "ID"


class AstNormalizer(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name):
        return ast.copy_location(ast.Name(id='ID', ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg):
        node.arg = 'ARG'
        return node

    def visit_Attribute(self, node: ast.Attribute):
        node = self.generic_visit(node)
        node.attr = 'ATTR'
        return node

    def visit_Constant(self, node: ast.Constant):
        # Replace constants with a tokenized representative
        return ast.copy_location(ast.Name(id='CONST', ctx=ast.Load()), node)


def ast_node_types(node: ast.AST) -> list[str]:
    return [type(n).__name__ for n in ast.walk(node)]


def make_shingles(tokens: list[str], k: int) -> list[str]:
    if k <= 1:
        return tokens
    shingles = []
    for i in range(0, len(tokens) - k + 1):
        shingles.append('|'.join(tokens[i:i+k]))
    return shingles


def parse_functions_from_module(module_ast: ast.AST, module_name: str) -> list[tuple[str, ast.AST, int, int]]:
    results: list[tuple[str, ast.AST, int, int]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope: list[str] = []

        def add_func(self, node: ast.AST, name: str):
            start = getattr(node, 'lineno', 0)
            end = getattr(node, 'end_lineno', start)
            qual = '.'.join([p for p in [module_name] + self.scope + [name] if p])
            results.append((qual, node, start, end))

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self.add_func(node, node.name)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self.add_func(node, node.name)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

    Visitor().visit(module_ast)
    return results


def extract_imports(module_ast: ast.AST) -> list[str]:
    modules: set[str] = set()
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add((alias.name or '').split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            m = (node.module or '').split('.')[0]
            if m:
                modules.add(m)
    return sorted(modules)


def parse_project_python(db: Session, project: Project):
    settings = Settings()

    # Clear old collected imports and functions for this project
    db.query(Function).filter(Function.project_id == project.id).delete(synchronize_session=False)
    db.query(ImportUsage).filter(ImportUsage.project_id == project.id).delete(synchronize_session=False)
    db.commit()

    for rel_path, full_path in iter_py_files(project.root_path):
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                src = f.read()
        except UnicodeDecodeError:
            # Skip non-UTF8
            continue
        size_bytes = len(src.encode('utf-8', errors='ignore'))
        sha = file_sha256(full_path)

        # Upsert file record
        code_file = db.query(CodeFile).filter_by(project_id=project.id, rel_path=rel_path).one_or_none()
        if code_file is None:
            code_file = CodeFile(project_id=project.id, rel_path=rel_path, sha256=sha, size_bytes=size_bytes)
            db.add(code_file)
            db.flush()
        else:
            code_file.sha256 = sha
            code_file.size_bytes = size_bytes

        module_name = os.path.splitext(rel_path.replace(os.sep, '.'))[0]

        try:
            tree = ast.parse(src)
        except SyntaxError:
            db.flush()
            continue

        # Imports
        for mod in extract_imports(tree):
            db.add(ImportUsage(project_id=project.id, file_id=code_file.id, module=mod))

        # Functions
        funcs = parse_functions_from_module(tree, module_name)
        for qualname, fn_node, start, end in funcs:
            # Skip very large functions
            if settings.MAX_FUNCTION_SIZE_LINES and end - start > settings.MAX_FUNCTION_SIZE_LINES:
                continue

            # Args signature
            args = []
            if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = fn_node.args
                def arg_names(args_list):
                    return [getattr(x, 'arg', None) or 'ARG' for x in args_list]
                parts = []
                parts += arg_names(getattr(a, 'posonlyargs', []))
                parts += arg_names(getattr(a, 'args', []))
                if a.vararg:
                    parts.append('*VARARG')
                parts += [f"{getattr(k.arg, 'arg', 'KW') or 'KW'}" for k in getattr(a, 'kwonlyargs', [])]
                if a.kwarg:
                    parts.append('**KWARG')
                args_signature = '(' + ','.join(['ARG' for _ in parts]) + ')'
            else:
                args_signature = '()'

            # Docstring
            doc = ast.get_docstring(fn_node)

            # AST normalization
            norm = AstNormalizer().visit(ast.fix_missing_locations(fn_node))
            ast_types = ast_node_types(norm)
            types_json = json.dumps(ast_types)
            ast_norm_hash = hashlib.sha256(types_json.encode('utf-8')).hexdigest()

            # Shingles on node types
            shingles = make_shingles(ast_types, settings.SHINGLE_SIZE)
            shingles_json = json.dumps(list(set(shingles)))

            db.add(Function(
                project_id=project.id,
                file_id=code_file.id,
                qualname=qualname,
                name=qualname.split('.')[-1],
                args_signature=args_signature,
                docstring=doc,
                start_line=start,
                end_line=end,
                ast_types_seq=types_json,
                ast_norm_hash=ast_norm_hash,
                token_shingles=shingles_json,
            ))

        db.flush()

    db.commit()

