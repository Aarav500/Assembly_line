import json
import os
from urllib.parse import urlencode

DEFAULT_HOST = "http://localhost:5000"


def _infer_sample_value(t):
    if isinstance(t, dict) and "type" in t:
        t = t["type"]
    if t in ("string", str):
        return "string"
    if t in ("integer", int):
        return 123
    if t in ("number", float):
        return 123.45
    if t in ("boolean", bool):
        return True
    if t == "array":
        return []
    if t == "object":
        return {}
    return "string"


def _example_from_schema(schema):
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties", {})
        example = {}
        for k, v in props.items():
            if isinstance(v, dict):
                if v.get("example") is not None:
                    example[k] = v["example"]
                elif v.get("type") == "array":
                    items = v.get("items") or {"type": "string"}
                    example[k] = [
                        _example_from_schema(items)
                        if isinstance(items, dict)
                        else _infer_sample_value(items)
                    ]
                elif v.get("type") == "object":
                    example[k] = _example_from_schema(v)
                else:
                    example[k] = _infer_sample_value(v.get("type"))
            else:
                example[k] = _infer_sample_value(v)
        return example
    if t == "array":
        items = schema.get("items") or {"type": "string"}
        base = _example_from_schema(items) if isinstance(items, dict) else _infer_sample_value(items)
        return [base]
    return _infer_sample_value(t)


def _build_query_example(query_def):
    q = {}
    for name, meta in (query_def or {}).items():
        if meta is None:
            continue
        if isinstance(meta, dict):
            if meta.get("example") is not None:
                q[name] = meta["example"]
            elif meta.get("default") is not None:
                q[name] = meta["default"]
            else:
                q[name] = _infer_sample_value(meta.get("type"))
        else:
            q[name] = _infer_sample_value(meta)
    return q


def _curl_example(base_url, path, method, query=None, body=None):
    url = f"{base_url}{path}"
    if query:
        url += ("?" + urlencode(query, doseq=True))
    parts = ["curl", "-X", method.upper(), f'"{url}"']
    headers = []
    data = None
    if body is not None and method.upper() in ("POST", "PUT", "PATCH"):
        headers.append("-H 'Content-Type: application/json'")
        data = json.dumps(body)
        parts.extend(headers)
        parts.extend(["-d", f"'{data}'"])
    else:
        parts.extend(headers)
    return " ".join(parts)


def _python_requests_example(base_url, path, method, query=None, body=None):
    url = f"{base_url}{path}"
    lines = ["import requests", f"url = \"{url}\""]
    if query:
        lines.append(f"params = {json.dumps(query, indent=2)}")
    if body is not None and method.upper() in ("POST", "PUT", "PATCH"):
        lines.append(f"payload = {json.dumps(body, indent=2)}")
    call = "requests.{}(url{}{})".format(
        method.lower(),
        ", params=params" if query else "",
        ", json=payload" if body is not None and method.upper() in ("POST", "PUT", "PATCH") else "",
    )
    lines.append(f"resp = {call}")
    lines.append("print(resp.status_code)")
    lines.append("print(resp.json() if resp.headers.get('Content-Type','').startswith('application/json') else resp.text)")
    return "\n".join(lines)


def _js_fetch_example(base_url, path, method, query=None, body=None):
    url = f"{base_url}{path}"
    if query:
        url += ("?" + urlencode(query))
    init = {"method": method.upper(), "headers": {}}
    if body is not None and method.upper() in ("POST", "PUT", "PATCH"):
        init["headers"]["Content-Type"] = "application/json"
        init["body"] = json.dumps(body)
    return (
        "fetch(\"{}\", {})\n  .then(res => res.json())\n  .then(console.log)\n  .catch(console.error);".format(url, json.dumps(init, indent=2))
    )


class DocGenerator:
    def __init__(self, app, base_url=DEFAULT_HOST):
        self.app = app
        self.base_url = base_url.rstrip("/")

    def collect(self):
        endpoints = []
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            view_fn = self.app.view_functions.get(rule.endpoint)
            if view_fn is None:
                continue
            meta = getattr(view_fn, "_endpoint_doc", {})
            description = (meta.get("description") or (view_fn.__doc__ or "")).strip()
            summary = meta.get("summary") or description.splitlines()[0] if description else rule.rule

            for method in sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS")):
                params = {}
                for arg in rule.arguments:
                    params[arg] = meta.get("params", {}).get(arg, {"type": "string", "required": True})
                query = meta.get("query", {})
                body_schema = meta.get("body") if method in ("POST", "PUT", "PATCH") else None
                body_example = _example_from_schema(body_schema) if body_schema else None
                query_example = _build_query_example(query)

                examples = meta.get("examples", {}).copy()
                if "curl" not in examples:
                    examples["curl"] = _curl_example(self.base_url, rule.rule, method, query_example, body_example)
                if "python" not in examples:
                    examples["python"] = _python_requests_example(self.base_url, rule.rule, method, query_example, body_example)
                if "javascript" not in examples:
                    examples["javascript"] = _js_fetch_example(self.base_url, rule.rule, method, query_example, body_example)

                endpoint_doc = {
                    "path": rule.rule,
                    "method": method,
                    "endpoint": rule.endpoint,
                    "summary": summary,
                    "description": description,
                    "params": params,
                    "query": query,
                    "body": body_schema or {},
                    "responses": meta.get("responses", {}),
                    "examples": examples,
                    "tags": meta.get("tags", []),
                }
                endpoints.append(endpoint_doc)
        return {
            "info": {
                "title": self.app.import_name,
                "version": "1.0.0",
                "base_url": self.base_url,
            },
            "endpoints": endpoints,
        }

    def to_markdown(self, model):
        lines = []
        info = model.get("info", {})
        lines.append(f"# {info.get('title', 'API Documentation')}")
        lines.append("")
        lines.append(f"Base URL: {info.get('base_url', '')}")
        lines.append("")
        for ep in model.get("endpoints", []):
            lines.append(f"## {ep['method']} {ep['path']}")
            if ep.get("summary"):
                lines.append(f"**Summary:** {ep['summary']}")
            if ep.get("description"):
                lines.append("")
                lines.append(ep["description"])
            if ep.get("params"):
                lines.append("")
                lines.append("Path Parameters:")
                for name, meta in ep["params"].items():
                    req = meta.get("required", False)
                    typ = meta.get("type", "string")
                    desc = meta.get("description", "")
                    lines.append(f"- {name} ({typ}){' [required]' if req else ''}: {desc}")
            if ep.get("query"):
                lines.append("")
                lines.append("Query Parameters:")
                for name, meta in ep["query"].items():
                    if isinstance(meta, dict):
                        req = meta.get("required", False)
                        typ = meta.get("type", "string")
                        desc = meta.get("description", "")
                        default = meta.get("default")
                        extra = f" Default: {default}" if default is not None else ""
                        lines.append(f"- {name} ({typ}){' [required]' if req else ''}: {desc}{extra}")
                    else:
                        lines.append(f"- {name}: {meta}")
            if ep.get("body"):
                lines.append("")
                lines.append("Request Body Schema:")
                lines.append("```")
                lines.append(json.dumps(ep["body"], indent=2))
                lines.append("```")
            if ep.get("responses"):
                lines.append("")
                lines.append("Responses:")
                for code, meta in ep["responses"].items():
                    desc = meta.get("description", "") if isinstance(meta, dict) else str(meta)
                    lines.append(f"- {code}: {desc}")
            if ep.get("examples"):
                lines.append("")
                lines.append("Examples:")
                if ep["examples"].get("curl"):
                    lines.append("```bash")
                    lines.append(ep["examples"]["curl"])
                    lines.append("```")
                if ep["examples"].get("python"):
                    lines.append("```python")
                    lines.append(ep["examples"]["python"])
                    lines.append("```")
                if ep["examples"].get("javascript"):
                    lines.append("```javascript")
                    lines.append(ep["examples"]["javascript"])
                    lines.append("```")
            lines.append("")
        return "\n".join(lines)

    def to_html(self, model):
        # Simple HTML generation using Markdown content wrapped in <pre> for examples
        md = self.to_markdown(model)
        # Minimal conversion: replace code fences with <pre><code>
        html = md
        html = html.replace("```bash", "<pre><code class=\"language-bash\">")
        html = html.replace("```python", "<pre><code class=\"language-python\">")
        html = html.replace("```javascript", "<pre><code class=\"language-javascript\">")
        html = html.replace("```", "</code></pre>")
        # Headings
        html = html.replace("\n# ", "\n<h1>").replace("\n## ", "\n<h2>")
        # Close headings
        lines = html.splitlines()
        fixed = []
        for line in lines:
            if line.startswith("<h1>"):
                fixed.append(line + "</h1>")
            elif line.startswith("<h2>"):
                fixed.append(line + "</h2>")
            else:
                fixed.append(f"<p>{line}</p>" if line.strip() and not line.startswith("<pre>") and not line.startswith("</code>") else line)
        style = (
            "<style>body{font-family:Arial,Helvetica,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;}"
            "pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:6px;overflow:auto;}"
            "code{font-family:ui-monospace,Menlo,Monaco,Consolas,monospace;}"
            "h1{border-bottom:1px solid #e5e7eb;padding-bottom:8px;}h2{margin-top:28px;}</style>"
        )
        return f"<html><head><meta charset='utf-8'><title>{model.get('info',{}).get('title','API Docs')}</title>{style}</head><body>" + "\n".join(fixed) + "</body></html>"

    def write_all(self, output_dir="docs"):
        os.makedirs(output_dir, exist_ok=True)
        model = self.collect()
        with open(os.path.join(output_dir, "api.json"), "w", encoding="utf-8") as f:
            json.dump(model, f, indent=2)
        with open(os.path.join(output_dir, "api.md"), "w", encoding="utf-8") as f:
            f.write(self.to_markdown(model))
        with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(self.to_html(model))
        return model

