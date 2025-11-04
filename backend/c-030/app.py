import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from datetime import timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, g, jsonify
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from db import init_db, insert_entry, query_entries, close_db
from forms import SubmitForm
import bleach

load_dotenv()

app = Flask(__name__, instance_relative_config=True)

# Ensure instance folder exists for DB and secrets
try:
    os.makedirs(app.instance_path, exist_ok=True)
except OSError:
    pass

# Basic logging (avoid logging PII)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("secure-app")

# Configuration
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", os.urandom(32)),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    WTF_CSRF_TIME_LIMIT=3600,
)

# CSRF Protection
csrf = CSRFProtect(app)

# Security headers similar to Helmet via Talisman
force_https = os.environ.get("FORCE_HTTPS", "false").lower() in ("1", "true", "yes")
content_security_policy = {
    "default-src": "'self'",
    "img-src": "'self' data:",
    "script-src": "'self'",
    "style-src": "'self' 'unsafe-inline'",  # allow inline styles for simplicity; avoid inline scripts
    "base-uri": "'self'",
    "frame-ancestors": "'none'",
    "object-src": "'none'",
}

Talisman(
    app,
    content_security_policy=content_security_policy,
    force_https=force_https,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    strict_transport_security_include_subdomains=True,
    strict_transport_security_preload=True,
    session_cookie_secure=True,
    frame_options="DENY",
    content_security_policy_nonce_in=[],
)

# Rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])

# DB teardown
app.teardown_appcontext(close_db)

# Initialize DB on first request
@app.before_first_request
def setup_app():
    init_db()

# Extra response hardening
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Remove server details if present
    response.headers.pop("Server", None)
    response.headers.pop("X-Powered-By", None)
    return response

# Input sanitization using bleach
ALLOWED_TAGS = ["b", "i", "em", "strong", "a", "code", "pre", "ul", "ol", "li"]
ALLOWED_ATTRS = {"a": ["href", "title", "rel", "target"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

def sanitize_comment(text: str) -> str:
    if not text:
        return ""
    cleaned = bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, protocols=ALLOWED_PROTOCOLS, strip=True)
    # Enforce safe links (nofollow, noopener, noreferrer) and no javascript: URIs
    def set_rel(attrs, new=False):
        href = attrs.get((None, "href"), "")
        if href and not any(href.lower().startswith(p + ":") for p in ALLOWED_PROTOCOLS):
            # Disallow non-allowed protocols
            return None
        rel = attrs.get((None, "rel"), "")
        rel_tokens = set(filter(None, (rel.split(" ") if rel else [])))
        rel_tokens.update(["nofollow", "noopener", "noreferrer"])
        attrs[(None, "rel")] = " ".join(sorted(rel_tokens))
        # avoid target=_blank if not desired; keep if present
        target = attrs.get((None, "target"))
        if target and target.lower() == "_blank":
            attrs[(None, "target")] = "_blank"
        return attrs
    linked = bleach.linkify(cleaned, callbacks=[set_rel], parse_email=True, skip_tags=["pre", "code"])
    return linked

@app.route("/", methods=["GET"])
def index():
    items = query_entries(limit=20)
    return render_template("index.html", items=items)

@app.route("/submit", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def submit():
    form = SubmitForm()
    if request.method == "POST":
        if form.validate_on_submit():
            # Trim inputs
            name = (form.name.data or "").strip()
            email = (form.email.data or "").strip().lower()
            comment_raw = (form.comment.data or "").strip()

            # Extra server-side normalization and constraints
            if len(name) > 50 or len(email) > 120 or len(comment_raw) > 1000:
                flash("Input too long.", "error")
                return redirect(url_for("submit"))

            # Sanitize comment HTML
            comment = sanitize_comment(comment_raw)

            try:
                insert_entry(name=name, email=email, comment=comment)
                flash("Submission saved securely.", "success")
                return redirect(url_for("index"))
            except Exception as e:
                logger.exception("DB insert failed (non-PII message)")
                flash("Unexpected error. Please try again later.", "error")
                return redirect(url_for("submit"))
        else:
            flash("Please correct the errors in the form.", "error")
    return render_template("submit.html", form=form)

@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app


@app.route('/users', methods=['POST'])
def _auto_stub_users():
    return 'Auto-generated stub for /users', 200
