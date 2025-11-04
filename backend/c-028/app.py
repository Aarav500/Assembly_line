import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, render_template, request, flash, redirect, url_for
from accessibility.generator import generate_form_spec, validate_form


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    app.config["APP_NAME"] = "A11y-First UI"

    @app.context_processor
    def inject_globals():
        return {
            "app_name": app.config["APP_NAME"],
            "lang": "en",
        }

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/form", methods=["GET", "POST"])
    def form():
        fields = generate_form_spec()
        values = {f["name"]: request.form.get(f["name"], f.get("default", "")) for f in fields}
        errors = {}

        if request.method == "POST":
            errors = validate_form(request.form)
            if not errors:
                flash("Form submitted successfully.", "success")
                return redirect(url_for("form"))
            else:
                flash("Please fix the errors in the form.", "error")

        return render_template("form.html", fields=fields, values=values, errors=errors)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
