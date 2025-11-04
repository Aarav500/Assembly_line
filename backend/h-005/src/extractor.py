import ast
import json as pyjson
import re
from typing import Dict, Any, Tuple
from .graph_store import GraphStore


class Extractor:
    def __init__(self, store: GraphStore):
        self.store = store

    def process_artifact(self, artifact_id: str, artifact_type: str, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        nodes_before = len(self.store.nodes)
        edges_before = len(self.store.edges)

        art_node = self.store.ensure_artifact(artifact_id, artifact_type, metadata)
        summary = {}

        at = (artifact_type or 'text').lower()
        if at == 'code':
            s = self._extract_from_code(artifact_id, content, art_node)
            summary['code'] = s
        elif at == 'json':
            s = self._extract_from_json(artifact_id, content, art_node)
            summary['json'] = s
        else:
            s = self._extract_from_text(artifact_id, content, art_node)
            summary['text'] = s

        return {
            "nodes_added": len(self.store.nodes) - nodes_before,
            "edges_added": len(self.store.edges) - edges_before,
            "summary": summary
        }

    # Code extraction (Python)
    def _extract_from_code(self, artifact_id: str, content: str, art_node: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(content)
        except Exception:
            return self._extract_from_text(artifact_id, content, art_node)

        defined_funcs = []
        defined_classes = []
        calls = []
        imports = []

        def node_for_func(name: str) -> str:
            nid = self.store.upsert_node(name=name, type_='FUNCTION', properties={})
            self.store.add_edge(nid, art_node, 'BELONGS_TO')
            self.store.add_edge(art_node, nid, 'DEFINES')
            return nid

        def node_for_class(name: str) -> str:
            nid = self.store.upsert_node(name=name, type_='CLASS', properties={})
            self.store.add_edge(nid, art_node, 'BELONGS_TO')
            self.store.add_edge(art_node, nid, 'DEFINES')
            return nid

        def node_for_module(name: str) -> str:
            return self.store.upsert_node(name=name, type_='MODULE', properties={})

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                defined_funcs.append(node.name)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                defined_funcs.append(node.name)
                self.generic_visit(node)

            def visit_ClassDef(self, node: ast.ClassDef):
                defined_classes.append(node.name)
                self.generic_visit(node)

            def visit_Import(self, node: ast.Import):
                for alias in node.names:
                    imports.append(alias.name)

            def visit_ImportFrom(self, node: ast.ImportFrom):
                mod = node.module or ''
                imports.append(mod)

        Visitor().visit(tree)

        # Build nodes for defs
        fn_nodes = {name: node_for_func(name) for name in set(defined_funcs)}
        cls_nodes = {name: node_for_class(name) for name in set(defined_classes)}

        # Process calls: walk and collect callee names within function bodies
        class CallCollector(ast.NodeVisitor):
            def __init__(self, current_fn: str):
                self.current_fn = current_fn

            def visit_Call(self, node: ast.Call):
                callee = self._name_from_expr(node.func)
                if callee:
                    calls.append((self.current_fn, callee))
                self.generic_visit(node)

            def _name_from_expr(self, e):
                if isinstance(e, ast.Name):
                    return e.id
                if isinstance(e, ast.Attribute):
                    # e.g., module.func or obj.method -> take attribute name
                    return e.attr
                return None

        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = CallCollector(n.name)
                cc.visit(n)
            if isinstance(n, ast.ClassDef):
                for item in n.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        mname = f"{n.name}.{item.name}"
                        # register method as function node as well
                        fn_nodes.setdefault(mname, node_for_func(mname))
                        cc = CallCollector(mname)
                        cc.visit(item)

        # Persist imports
        for mod in set([m for m in imports if m]):
            mnode = node_for_module(mod)
            self.store.add_edge(art_node, mnode, 'IMPORTS')

        # Persist calls
        for caller, callee in set(calls):
            caller_id = fn_nodes.get(caller) or self.store.upsert_node(caller, 'FUNCTION', {})
            callee_id = fn_nodes.get(callee) or self.store.upsert_node(callee, 'FUNCTION', {})
            self.store.add_edge(caller_id, callee_id, 'CALLS')

        return {
            "functions": sorted(set(defined_funcs)),
            "classes": sorted(set(defined_classes)),
            "imports": sorted(set([m for m in imports if m])),
            "calls": sorted(set([f"{c}->{d}" for c, d in calls]))
        }

    # Text/Markdown extraction
    def _extract_from_text(self, artifact_id: str, content: str, art_node: str) -> Dict[str, Any]:
        summary = {
            "mentions": [],
            "relations": []
        }
        text = content or ''

        # Backtick identifiers
        for ident in set(re.findall(r"`([^`]+)`", text)):
            ent = self.store.upsert_node(ident.strip(), 'IDENTIFIER', {})
            self.store.add_edge(art_node, ent, 'MENTIONS')
            summary['mentions'].append(ident.strip())

        # Issue-like IDs
        issue_pattern = re.compile(r"\b([A-Z]{2,10}-\d+|#\d+)\b")
        for token in set(issue_pattern.findall(text)):
            ent = self.store.upsert_node(token, 'ISSUE', {})
            self.store.add_edge(art_node, ent, 'MENTIONS')
            summary['mentions'].append(token)

        # Person like Names: capitalized first+last
        for person in set(re.findall(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", text)):
            pnode = self.store.upsert_node(person, 'PERSON', {})
            self.store.add_edge(art_node, pnode, 'MENTIONS')
            summary['mentions'].append(person)

        # Headings as components
        for heading in set(re.findall(r"^#+\s+(.+)$", text, flags=re.MULTILINE)):
            comp = heading.strip()
            cnode = self.store.upsert_node(comp, 'COMPONENT', {})
            self.store.add_edge(art_node, cnode, 'MENTIONS')
            summary['mentions'].append(comp)

        # Relation patterns
        patterns = [
            (r"\b(.+?)\s+depends on\s+(.+?)\b", 'DEPENDS_ON'),
            (r"\b(.+?)\s+uses\s+(.+?)\b", 'USES'),
            (r"\b(.+?)\s+calls\s+(.+?)\b", 'CALLS'),
            (r"\b(.+?)\s+related to\s+(.+?)\b", 'RELATED'),
        ]
        # Author/owner
        authored = re.findall(r"\bauthored by\s+([^\n\r\.]+)", text, flags=re.IGNORECASE)
        for who in set([w.strip() for w in authored if w.strip()]):
            pnode = self.store.upsert_node(who, 'PERSON', {})
            self.store.add_edge(art_node, pnode, 'AUTHORED_BY')
            summary['relations'].append({"AUTHORED_BY": who})

        owned = re.findall(r"\bowned by\s+([^\n\r\.]+)", text, flags=re.IGNORECASE)
        for who in set([w.strip() for w in owned if w.strip()]):
            pnode = self.store.upsert_node(who, 'PERSON', {})
            self.store.add_edge(art_node, pnode, 'OWNED_BY')
            summary['relations'].append({"OWNED_BY": who})

        # Process line by line to avoid greedy captures
        for line in text.splitlines():
            l = line.strip()
            if not l:
                continue
            for pat, label in patterns:
                for a, b in re.findall(pat, l, flags=re.IGNORECASE):
                    src = a.strip().strip('`').strip('.')
                    dst = b.strip().strip('`').strip('.')
                    if not src or not dst:
                        continue
                    # choose type heuristics
                    stype = 'COMPONENT'
                    dtype = 'COMPONENT'
                    if label == 'CALLS':
                        stype = 'FUNCTION'
                        dtype = 'FUNCTION'
                    s_id = self.store.upsert_node(src, stype, {})
                    d_id = self.store.upsert_node(dst, dtype, {})
                    self.store.add_edge(s_id, d_id, label)
                    # tie mentions to artifact
                    self.store.add_edge(art_node, s_id, 'MENTIONS')
                    self.store.add_edge(art_node, d_id, 'MENTIONS')
                    summary['relations'].append({label: f"{src} -> {dst}"})

        return summary

    # JSON extraction
    def _extract_from_json(self, artifact_id: str, content: str, art_node: str) -> Dict[str, Any]:
        try:
            data = pyjson.loads(content)
        except Exception:
            return self._extract_from_text(artifact_id, content, art_node)

        summary = {"keys": 0, "string_refs": 0}

        def walk(obj, parent_name: str):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key_node = self.store.upsert_node(f"{parent_name}.{k}" if parent_name else str(k), 'FIELD', {})
                    self.store.add_edge(art_node, key_node, 'CONTAINS')
                    summary['keys'] += 1
                    walk(v, f"{parent_name}.{k}" if parent_name else str(k))
            elif isinstance(obj, list):
                for idx, v in enumerate(obj):
                    walk(v, f"{parent_name}[{idx}]")
            else:
                if isinstance(obj, str):
                    # detect references like module:function or ISSUE IDs
                    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:[A-Za-z_][A-Za-z0-9_]*$", obj):
                        left, right = obj.split(':', 1)
                        mnode = self.store.upsert_node(left, 'MODULE', {})
                        fnode = self.store.upsert_node(right, 'FUNCTION', {})
                        self.store.add_edge(mnode, fnode, 'EXPOSES')
                        self.store.add_edge(art_node, fnode, 'MENTIONS')
                        summary['string_refs'] += 1
                    for token in re.findall(r"\b([A-Z]{2,10}-\d+|#\d+)\b", obj):
                        inode = self.store.upsert_node(token, 'ISSUE', {})
                        self.store.add_edge(art_node, inode, 'MENTIONS')
                        summary['string_refs'] += 1
        walk(data, '')
        return summary

