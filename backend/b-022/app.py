import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, Response
from tokens import DEFAULT_TOKENS, sanitize_tokens, to_css_variables_block, flatten_tokens

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")


def get_tokens():
    tokens = session.get("tokens")
    if not tokens:
        tokens = DEFAULT_TOKENS
    return tokens


@app.route("/")
def index():
    tokens = get_tokens()
    pretty_json = json.dumps(tokens, indent=2, ensure_ascii=False)
    return render_template("index.html", tokens_json=pretty_json)


@app.route("/generate", methods=["POST"])
def generate():
    source = request.form.get("source", "json")
    tokens = None

    if source == "json":
        raw = request.form.get("tokens_json", "").strip()
        if not raw:
            tokens = DEFAULT_TOKENS
        else:
            try:
                parsed = json.loads(raw)
                tokens = sanitize_tokens(parsed, fallback=DEFAULT_TOKENS)
            except Exception:
                tokens = DEFAULT_TOKENS
    else:
        # Quick editor fields fallback into DEFAULT_TOKENS structure
        base = json.loads(json.dumps(DEFAULT_TOKENS))  # deep copy
        def get(name, default):
            v = request.form.get(name, "").strip()
            return v or default
        # Colors
        base["colors"]["primary"] = get("color_primary", base["colors"]["primary"]) 
        base["colors"]["secondary"] = get("color_secondary", base["colors"]["secondary"]) 
        base["colors"]["background"] = get("color_background", base["colors"]["background"]) 
        base["colors"]["surface"] = get("color_surface", base["colors"]["surface"]) 
        base["colors"]["text"]["primary"] = get("color_text_primary", base["colors"]["text"]["primary"]) 
        base["colors"]["text"]["secondary"] = get("color_text_secondary", base["colors"]["text"]["secondary"]) 
        base["colors"]["text"]["inverse"] = get("color_text_inverse", base["colors"]["text"]["inverse"]) 
        base["colors"]["states"]["success"] = get("color_success", base["colors"]["states"]["success"]) 
        base["colors"]["states"]["warning"] = get("color_warning", base["colors"]["states"]["warning"]) 
        base["colors"]["states"]["error"] = get("color_error", base["colors"]["states"]["error"]) 
        base["colors"]["states"]["info"] = get("color_info", base["colors"]["states"]["info"]) 
        # Typography scale examples (optional)
        for k in list(base.get("typography", {}).get("scale", {}).keys()):
            base["typography"]["scale"][k] = get(f"type_scale_{k}", base["typography"]["scale"][k])
        tokens = sanitize_tokens(base, fallback=DEFAULT_TOKENS)

    session["tokens"] = tokens
    return redirect(url_for("guide"))


@app.route("/guide")
def guide():
    tokens = get_tokens()
    flat = flatten_tokens(tokens)
    css_vars_block, css_var_map = to_css_variables_block(tokens, return_map=True)
    pretty_json = json.dumps(tokens, indent=2, ensure_ascii=False)
    return render_template(
        "style_guide.html",
        tokens=tokens,
        flat=flat,
        css_vars_block=css_vars_block,
        css_var_map=css_var_map,
        tokens_json=pretty_json,
    )


@app.route("/export/json")
def export_json():
    tokens = get_tokens()
    data = json.dumps(tokens, indent=2, ensure_ascii=False)
    return Response(
        data,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=design-tokens.json"},
    )


@app.route("/export/css")
def export_css():
    tokens = get_tokens()
    css_vars_block = to_css_variables_block(tokens)
    content = f"/* Design Tokens CSS Variables */\n{css_vars_block}\n"
    return Response(
        content,
        mimetype="text/css",
        headers={"Content-Disposition": "attachment; filename=design-tokens.css"},
    )


@app.route("/reset")
def reset():
    session.pop("tokens", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app


@app.route('/api/generate', methods=['GET'])
def _auto_stub_api_generate():
    return 'Auto-generated stub for /api/generate', 200
