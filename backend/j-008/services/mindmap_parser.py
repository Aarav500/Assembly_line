import re
import json
from typing import List, Tuple, Dict, Any

INDENT = 2

class Node:
    def __init__(self, text: str):
        self.text = text.strip()
        self.children: List["Node"] = []
    def __repr__(self):
        return f"Node(text={self.text!r}, children={len(self.children)})"


def parse_tree(text: str) -> List[Node]:
    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    root: List[Node] = []
    stack: List[Tuple[int, Node]] = []  # (depth, node)

    for raw in lines:
        if not raw.strip():
            continue
        if raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        depth = indent // INDENT
        node = Node(raw.strip())

        while stack and stack[-1][0] >= depth:
            stack.pop()
        if not stack:
            root.append(node)
        else:
            stack[-1][1].children.append(node)
        stack.append((depth, node))
    return root


def slugify(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9\s/_-]", "", t)
    t = t.replace("/", "-")
    t = re.sub(r"\s+", "-", t)
    t = re.sub(r"-+", "-", t)
    t = t.strip("-")
    return t or "item"


def to_route(name: str) -> str:
    s = slugify(name)
    if s in ("home", "index", "root"):
        return "/"
    return f"/{s}"


def extract_value(text: str) -> Tuple[str, str]:
    # returns (key_lower, value) when pattern "Key: value" else (text_lower, "")
    if ":" in text:
        k, v = text.split(":", 1)
        return k.strip().lower(), v.strip()
    return text.strip().lower(), ""


def parse_fields(spec: str) -> List[Dict[str, str]]:
    fields: List[Dict[str, str]] = []
    if not spec:
        return fields
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for p in parts:
        if ":" in p:
            n, t = p.split(":", 1)
            fields.append({"name": n.strip(), "type": t.strip() or "str"})
        else:
            fields.append({"name": p.strip(), "type": "str"})
    return fields


def find_node(nodes: List[Node], names: List[str]) -> Node:
    names_lower = [n.lower() for n in names]
    for n in nodes:
        t = n.text.split(":", 1)[0].strip().lower()
        if t in names_lower:
            return n
    return None


def parse_models(node: Node) -> List[Dict[str, Any]]:
    models = []
    if not node:
        return models
    for child in node.children:
        key, rest = extract_value(child.text)
        model_name = child.text.split(":", 1)[0].strip() if rest else child.text.strip()
        fields = []
        if rest:
            fields = parse_fields(rest)
        else:
            for fch in child.children:
                _, spec = extract_value(fch.text)
                if ":" in fch.text:
                    n, t = fch.text.split(":", 1)
                    fields.append({"name": n.strip(), "type": t.strip() or "str"})
                else:
                    fields.append({"name": fch.text.strip(), "type": "str"})
        models.append({
            "name": model_name.strip(),
            "fields": fields
        })
    return models


def parse_pages(node: Node) -> List[Dict[str, str]]:
    pages = []
    if not node:
        return pages
    for child in node.children:
        # Allow "Name: /route" or plain name
        if ":" in child.text:
            n, r = child.text.split(":", 1)
            name = n.strip()
            route = r.strip() or to_route(name)
        else:
            name = child.text.strip()
            route = to_route(name)
        pages.append({"name": name, "route": route})
    return pages


def parse_apis(node: Node) -> List[Dict[str, str]]:
    apis = []
    if not node:
        return apis
    for child in node.children:
        text = child.text
        # Patterns: "METHOD /path -> handler" or "METHOD /path"
        m = re.match(r"^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+([^\s]+)(?:\s*->\s*([A-Za-z0-9_\-]+))?", text, re.IGNORECASE)
        if m:
            method = m.group(1).upper()
            path = m.group(2)
            handler = m.group(3)
            if not handler:
                handler = f"{method.lower()}_" + re.sub(r"[^a-z0-9]+", "_", path.strip("/").lower() or "root")
            apis.append({
                "method": method,
                "path": path,
                "handler": handler
            })
        else:
            # If unrecognized, treat line as path with GET
            path = text.strip()
            if not path:
                continue
            method = "GET"
            handler = f"get_" + re.sub(r"[^a-z0-9]+", "_", path.strip("/").lower() or "root")
            apis.append({"method": method, "path": path, "handler": handler})
    return apis


def mindmap_to_manifest(text: str) -> Tuple[Dict[str, Any], List[str]]:
    if not text or not text.strip():
        raise ValueError("Mindmap text is empty")
    tree = parse_tree(text)
    warnings: List[str] = []

    # Project name
    project_name = "MyApp"
    proj_node = find_node(tree, ["Project", "App", "Application"])
    if proj_node:
        # Accept formats: "Project: Name" or child contains name
        if ":" in proj_node.text:
            _, val = proj_node.text.split(":", 1)
            project_name = val.strip() or project_name
        else:
            if proj_node.children:
                child_text = proj_node.children[0].text
                if ":" in child_text:
                    _, val = child_text.split(":", 1)
                    project_name = val.strip() or project_name
                else:
                    project_name = child_text.strip() or project_name
    else:
        warnings.append("Project name not found. Defaulting to 'MyApp'. Add 'Project: YourName'.")

    pages_node = find_node(tree, ["Pages", "Screens", "Views"])
    pages = parse_pages(pages_node)
    if not pages:
        pages = [{"name": "Home", "route": "/"}]
        warnings.append("No pages found. Added default 'Home' page at '/'.")

    models_node = find_node(tree, ["Models", "Entities", "Data Models", "Schema"])
    models = parse_models(models_node)

    apis_node = find_node(tree, ["APIs", "API", "Endpoints", "Routes"])
    apis = parse_apis(apis_node)

    manifest: Dict[str, Any] = {
        "project": {"name": project_name},
        "pages": pages,
        "models": models,
        "apis": apis
    }
    return manifest, warnings

