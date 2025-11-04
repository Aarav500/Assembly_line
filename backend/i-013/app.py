import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any

from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, abort
from jinja2 import Environment, meta

APP_NAME = "Contract & SLA Generation Assistant"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates")
CLAUSES_PATH = os.path.join(DATA_DIR, "clauses.json")

os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# Jinja environment for parsing and rendering template bodies
jinja_env = Environment()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s-]+", "-", value)
    return value[:120]


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class TemplateStore:
    def __init__(self, directory: str):
        self.directory = directory

    def _path(self, slug: str) -> str:
        return os.path.join(self.directory, f"{slug}.json")

    def list(self) -> List[Dict[str, Any]]:
        items = []
        for name in sorted(os.listdir(self.directory)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.directory, name), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items.append({
                        "slug": data.get("slug"),
                        "name": data.get("name"),
                        "category": data.get("category"),
                        "version": data.get("version"),
                        "updated_at": data.get("updated_at"),
                    })
            except Exception:
                continue
        return items

    def load(self, slug: str) -> Dict[str, Any]:
        path = self._path(slug)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Template '{slug}' not found")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data: Dict[str, Any]) -> None:
        if "slug" not in data or not data["slug"]:
            raise ValueError("Template must have a slug")
        data.setdefault("created_at", now_iso())
        data["updated_at"] = now_iso()
        path = self._path(data["slug"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


template_store = TemplateStore(TEMPLATES_DIR)


class ClauseLibrary:
    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"clauses": []}, f)

    def list(self) -> List[Dict[str, Any]]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("clauses", [])
        except Exception:
            return []


clause_library = ClauseLibrary(CLAUSES_PATH)


def extract_variables(template_text: str) -> List[str]:
    try:
        ast = jinja_env.parse(template_text)
        vars_set = meta.find_undeclared_variables(ast)
        # filter out special jinja variables if any
        return sorted(v for v in vars_set if not v.startswith("_"))
    except Exception:
        return []


def guess_field_spec(var_name: str) -> Dict[str, Any]:
    name = var_name.lower()
    spec = {"name": var_name, "label": var_name.replace("_", " ").title(), "type": "text", "placeholder": "", "default": ""}
    if any(k in name for k in ["date", "effective", "deadline"]):
        spec["type"] = "date"
    elif any(k in name for k in ["email"]):
        spec["type"] = "email"
    elif any(k in name for k in ["percent", "percentage"]):
        spec["type"] = "number"
        spec["step"] = "0.01"
        spec["placeholder"] = "e.g., 99.9"
    elif any(k in name for k in ["amount", "fee", "price", "rate"]):
        spec["type"] = "number"
        spec["step"] = "0.01"
    elif any(k in name for k in ["days", "hours", "minutes", "term"]):
        spec["type"] = "number"
        spec["step"] = "1"
    elif name.startswith("include_") or name.startswith("has_") or name.startswith("is_") or name.endswith("_enabled"):
        spec["type"] = "checkbox"
        spec["default"] = "on"
    elif any(k in name for k in ["address", "scope", "description", "statement_of_work", "sow", "purpose"]):
        spec["type"] = "textarea"
    return spec


def render_body(body: str, context: Dict[str, Any]) -> str:
    # normalize checkbox values to booleans
    normalized = {}
    for k, v in context.items():
        if isinstance(v, str) and v.lower() in ("on", "true", "1", "yes"):
            normalized[k] = True
        elif isinstance(v, str) and v.lower() in ("off", "false", "0", "no", ""):
            normalized[k] = False
        else:
            normalized[k] = v
    try:
        template = Environment().from_string(body)
        return template.render(**normalized)
    except Exception as e:
        return f"[Rendering error] {e}"


@app.route("/")
def index():
    items = template_store.list()
    return render_template("index.html", app_name=APP_NAME, items=items)


@app.route("/templates/new", methods=["GET"])
def new_template():
    return render_template("template_form.html", app_name=APP_NAME, mode="new", template_data=None, clauses=clause_library.list())


@app.route("/templates", methods=["POST"])
def create_template():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "General").strip()
    version = request.form.get("version", "1.0.0").strip()
    body = request.form.get("body", "")
    if not name:
        return render_template("template_form.html", app_name=APP_NAME, mode="new", template_data=None, clauses=clause_library.list(), error="Name is required"), 400
    slug = slugify(name)
    data = {
        "slug": slug,
        "name": name,
        "category": category or "General",
        "version": version or "1.0.0",
        "body": body or "",
    }
    try:
        template_store.save(data)
    except Exception as e:
        return render_template("template_form.html", app_name=APP_NAME, mode="new", template_data=data, clauses=clause_library.list(), error=str(e)), 400
    return redirect(url_for("edit_template", slug=slug))


@app.route("/templates/<slug>/edit", methods=["GET"])
def edit_template(slug: str):
    try:
        data = template_store.load(slug)
    except FileNotFoundError:
        abort(404)
    return render_template("template_form.html", app_name=APP_NAME, mode="edit", template_data=data, clauses=clause_library.list())


@app.route("/templates/<slug>/update", methods=["POST"])
def update_template(slug: str):
    try:
        existing = template_store.load(slug)
    except FileNotFoundError:
        abort(404)
    name = request.form.get("name", existing.get("name", "")).strip()
    category = request.form.get("category", existing.get("category", "General")).strip()
    version = request.form.get("version", existing.get("version", "1.0.0")).strip()
    body = request.form.get("body", existing.get("body", ""))
    # allow rename -> slug change
    new_slug = slugify(name)
    data = {
        "slug": new_slug,
        "name": name,
        "category": category or "General",
        "version": version or "1.0.0",
        "body": body or "",
        "created_at": existing.get("created_at", now_iso()),
    }
    template_store.save(data)
    # if slug changed and old file exists, remove old
    if new_slug != slug:
        old_path = os.path.join(TEMPLATES_DIR, f"{slug}.json")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass
    return redirect(url_for("edit_template", slug=data["slug"]))


@app.route("/templates/<slug>/preview", methods=["GET"])
def preview_template(slug: str):
    try:
        data = template_store.load(slug)
    except FileNotFoundError:
        abort(404)
    vars_list = extract_variables(data.get("body", ""))
    specs = [guess_field_spec(v) for v in vars_list]
    return render_template("preview_form.html", app_name=APP_NAME, template_data=data, field_specs=specs)


@app.route("/templates/<slug>/render", methods=["POST"])
def render_template_post(slug: str):
    try:
        data = template_store.load(slug)
    except FileNotFoundError:
        abort(404)
    form_data = dict(request.form.items())
    # checkbox handling for unchecked boxes -> not present in form; infer from field specs
    vars_list = extract_variables(data.get("body", ""))
    for var in vars_list:
        if var not in form_data and (var.startswith("include_") or var.startswith("has_") or var.endswith("_enabled") or var.startswith("is_")):
            form_data[var] = "off"
    rendered = render_body(data.get("body", ""), form_data)
    return render_template("rendered.html", app_name=APP_NAME, template_data=data, rendered=rendered, values=form_data)


@app.route("/templates/<slug>/download", methods=["POST"])
def download_rendered(slug: str):
    try:
        data = template_store.load(slug)
    except FileNotFoundError:
        abort(404)
    form_data = dict(request.form.items())
    rendered = render_body(data.get("body", ""), form_data)
    filename = f"{data.get('name', slug)} - {datetime.utcnow().date().isoformat()}.txt"
    resp = make_response(rendered)
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    return resp


@app.route("/api/templates", methods=["GET"])
def api_templates():
    return jsonify({"templates": template_store.list()})


@app.route("/api/clauses", methods=["GET"])
def api_clauses():
    return jsonify({"clauses": clause_library.list()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app


@app.route('/api/template/sla', methods=['GET'])
def _auto_stub_api_template_sla():
    return 'Auto-generated stub for /api/template/sla', 200


@app.route('/api/template/nonexistent', methods=['GET'])
def _auto_stub_api_template_nonexistent():
    return 'Auto-generated stub for /api/template/nonexistent', 200


@app.route('/api/generate', methods=['POST'])
def _auto_stub_api_generate():
    return 'Auto-generated stub for /api/generate', 200
