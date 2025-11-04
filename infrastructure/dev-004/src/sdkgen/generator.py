import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"

@dataclass
class SecurityScheme:
    name: str
    type: str
    in_: Optional[str] = None
    key_name: Optional[str] = None
    scheme: Optional[str] = None
    bearer_format: Optional[str] = None

@dataclass
class ParamName:
    original: str
    py: str
    ts: str
    go: str

@dataclass
class Endpoint:
    method: str
    path: str
    summary: str
    operation_id: str
    path_params: List[ParamName]
    has_body: bool
    consumes_json: bool
    produces_json: bool
    security: List[Dict[str, List[str]]]
    python_name: str
    ts_name: str
    go_name: str
    ts_path_template: str
    py_path_template: str
    go_path_fmt: str
    go_path_fmt_args: List[str]


def _load_spec(spec_path: Path) -> Dict[str, Any]:
    text = spec_path.read_text(encoding="utf-8")
    try:
        if spec_path.suffix.lower() in [".yaml", ".yml"]:
            return yaml.safe_load(text)
        return json.loads(text)
    except Exception as e:
        raise RuntimeError(f"Failed to parse spec {spec_path}: {e}")


def _snake_case(name: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z_]+", "_", name)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    s2 = s2.replace("__", "_").strip("_").lower()
    if re.match(r"^[0-9]", s2):
        s2 = f"p_{s2}"
    return s2 or "op"


def _camel_case(name: str, pascal: bool = False) -> str:
    name = re.sub(r"[^0-9a-zA-Z]+", " ", name)
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "Op" if pascal else "op"
    parts = [p.lower() for p in parts]
    if pascal:
        return "".join(p.capitalize() for p in parts)
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _sanitize_ident(name: str, lang: str) -> str:
    if lang == "python":
        return _snake_case(name)
    if lang == "ts":
        base = _camel_case(name, pascal=False)
        if re.match(r"^[0-9]", base):
            base = f"p{base}"
        return base or "param"
    if lang == "go":
        base = _camel_case(name, pascal=False)
        if re.match(r"^[0-9]", base):
            base = f"p{base}"
        return base or "param"
    return name


def _build_operation_id(method: str, path: str) -> str:
    segs = [s for s in path.split('/') if s]
    segs = [re.sub(r"[^0-9a-zA-Z]+", "_", s) for s in segs]
    base = f"{method}_" + "_".join(segs)
    return base


def _collect_security_schemes(spec: Dict[str, Any]) -> Dict[str, SecurityScheme]:
    comps = spec.get("components", {})
    sec = comps.get("securitySchemes", {}) or {}
    out: Dict[str, SecurityScheme] = {}
    for name, s in sec.items():
        t = s.get("type")
        if t == "apiKey":
            out[name] = SecurityScheme(
                name=name,
                type=t,
                in_=s.get("in"),
                key_name=s.get("name"),
            )
        elif t == "http":
            out[name] = SecurityScheme(
                name=name,
                type=t,
                scheme=s.get("scheme"),
                bearer_format=s.get("bearerFormat"),
            )
        elif t == "oauth2":
            # treat as bearer for client purposes
            out[name] = SecurityScheme(
                name=name,
                type=t,
                scheme="bearer",
            )
        else:
            out[name] = SecurityScheme(name=name, type=t or "unknown")
    return out


def _ordered_path_params(path: str) -> List[str]:
    return re.findall(r"{([^}]+)}", path)


def _collect_params(path_item: Dict[str, Any], op: Dict[str, Any]) -> List[Dict[str, Any]]:
    params = []
    for p in (path_item.get("parameters") or []) + (op.get("parameters") or []):
        params.append(p)
    # de-dup by name+in
    seen = set()
    uniq = []
    for p in params:
        key = (p.get("name"), p.get("in"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _endpoint_from(spec: Dict[str, Any], path: str, method: str, op: Dict[str, Any]) -> Endpoint:
    path_item = spec.get("paths", {}).get(path, {})
    params = _collect_params(path_item, op)
    path_param_names = [p.get("name") for p in params if p.get("in") == "path"]
    # Ensure ordering matches template
    ordered = _ordered_path_params(path)
    # Keep only those actually in path
    ordered = [p for p in ordered if p in path_param_names]

    pn: List[ParamName] = []
    for n in ordered:
        pn.append(ParamName(
            original=n,
            py=_sanitize_ident(n, "python"),
            ts=_sanitize_ident(n, "ts"),
            go=_sanitize_ident(n, "go"),
        ))

    operation_id = op.get("operationId") or _build_operation_id(method, path)
    summary = op.get("summary") or op.get("description") or operation_id

    consumes_json = False
    if op.get("requestBody"):
        for ct in (op["requestBody"].get("content") or {}).keys():
            if ct.startswith("application/json"):
                consumes_json = True
                break
    produces_json = False
    for resp in (op.get("responses") or {}).values():
        for ct in (resp.get("content") or {}).keys():
            if ct.startswith("application/json"):
                produces_json = True
                break

    security = op.get("security") if op.get("security") is not None else spec.get("security", []) or []

    # Build language-specific names
    py_name = _snake_case(operation_id)
    ts_name = _camel_case(operation_id, pascal=False)
    go_name = _camel_case(operation_id, pascal=True)

    # Build path templates
    # Python f-string: replace {orig} with {py}
    py_path = path
    for p in pn:
        py_path = py_path.replace("{" + p.original + "}", "{" + p.py + "}")
    py_path_tmpl = f"{py_path}"

    # TS template literal: replace {orig} with ${encodeURIComponent(String(ts))}
    ts_path = path
    for p in pn:
        ts_path = ts_path.replace("{" + p.original + "}", "${encodeURIComponent(String(" + p.ts + "))}")

    # Go fmt: replace {orig} with %v, build args
    go_fmt = path
    go_args = []
    for p in pn:
        go_fmt = go_fmt.replace("{" + p.original + "}", "%v")
        go_args.append(p.go)

    return Endpoint(
        method=method.upper(),
        path=path,
        summary=summary,
        operation_id=operation_id,
        path_params=pn,
        has_body=bool(op.get("requestBody")),
        consumes_json=consumes_json,
        produces_json=produces_json,
        security=security,
        python_name=py_name,
        ts_name=ts_name,
        go_name=go_name,
        ts_path_template=ts_path,
        py_path_template=py_path_tmpl,
        go_path_fmt=go_fmt,
        go_path_fmt_args=go_args,
    )


def _collect_endpoints(spec: Dict[str, Any]) -> List[Endpoint]:
    endpoints: List[Endpoint] = []
    paths = spec.get("paths", {})
    for path, item in paths.items():
        for method in ["get", "post", "put", "delete", "patch", "head", "options"]:
            if method in item:
                op = item[method]
                endpoints.append(_endpoint_from(spec, path, method, op))
    return endpoints


def generate_sdks(spec_path: Path, out_dir: Path, languages: List[str]) -> None:
    spec = _load_spec(spec_path)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(disabled_extensions=(".j2",))
    )

    title = spec.get("info", {}).get("title") or "api"
    version = spec.get("info", {}).get("version") or "0.0.0"
    servers = spec.get("servers") or []
    base_url = servers[0].get("url") if servers else ""

    sec_schemes = _collect_security_schemes(spec)
    endpoints = _collect_endpoints(spec)

    ctx = {
        "title": title,
        "version": version,
        "base_url": base_url,
        "security_schemes": list(sec_schemes.values()),
        "endpoints": endpoints,
        "package_name_ts": _snake_case(title).replace("_", "-") or "api-client",
        "module_name_go": re.sub(r"[^0-9a-zA-Z_/]+", "", _snake_case(title).replace("_", "")) or "client",
    }

    if "python" in languages:
        py_dir = out_dir / "python"
        py_dir.mkdir(parents=True, exist_ok=True)
        template = env.get_template("python/client.py.j2")
        (py_dir / "client.py").write_text(template.render(**ctx), encoding="utf-8")

    if "typescript" in languages:
        ts_dir = out_dir / "typescript"
        ts_dir.mkdir(parents=True, exist_ok=True)
        template = env.get_template("typescript/client.ts.j2")
        (ts_dir / "client.ts").write_text(template.render(**ctx), encoding="utf-8")
        pkg = env.get_template("typescript/package.json.j2")
        (ts_dir / "package.json").write_text(pkg.render(**ctx), encoding="utf-8")

    if "go" in languages:
        go_dir = out_dir / "go" / "client"
        go_dir.mkdir(parents=True, exist_ok=True)
        template = env.get_template("go/client.go.j2")
        (go_dir / "client.go").write_text(template.render(**ctx), encoding="utf-8")
        gomod = env.get_template("go/go.mod.j2")
        (go_dir.parent / "go.mod").write_text(gomod.render(**ctx), encoding="utf-8")

