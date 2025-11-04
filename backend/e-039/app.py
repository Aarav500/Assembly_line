import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import os
from flask import Flask, jsonify, request, render_template, abort
from config import config
from models import upsert_site, get_site, list_sites, create_job, update_job, get_job, list_jobs
from jobs import JobWorker, new_job_id
from prerender import render_paths
from cdn import get_cdn_provider
from utils import iso_now
import queue

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

_job_queue = queue.Queue()
_workers = []
_cdn = None

_posts = []


def load_posts():
    global _posts
    content_path = os.path.join(os.getcwd(), "content", "posts.json")
    try:
        with open(content_path, "r", encoding="utf-8") as f:
            _posts = json.load(f)
    except FileNotFoundError:
        _posts = []


def default_site_routes() -> list:
    routes = ["/", "/about"]
    for p in _posts:
        slug = p.get("slug")
        if slug:
            routes.append(f"/blog/{slug}")
    return routes


def _job_handler(job: dict):
    job_id = job["id"]
    site_slug = job["site_slug"]
    paths = job["paths"]
    update_job(job_id, status="running")
    try:
        result = render_paths(app=job["app"], site_slug=site_slug, paths=paths, build_root=config.BUILD_ROOT)
        changed = result.changed
        cdn_result = None
        if changed:
            try:
                cdn_result = _cdn.purge(changed)
            except Exception as e:
                logger.exception("CDN purge failed: %s", e)
                cdn_result = {"error": str(e)}
        summary = {
            "written": len(result.written),
            "changed": len(result.changed),
            "skipped": len(result.skipped),
            "errors": result.errors,
            "cdn": cdn_result,
            "finished_at": iso_now(),
        }
        update_job(job_id, status="done", result=summary)
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        update_job(job_id, status="failed", error=str(e))


def start_workers(app, count: int):
    global _workers
    for i in range(count):
        w = JobWorker(_job_queue, _job_handler, name=f"worker-{i+1}")
        w.start()
        _workers.append(w)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    # Load posts for demo dynamic route(s)
    load_posts()

    global _cdn
    _cdn = get_cdn_provider(config)

    # Demo site pages
    @app.route("/")
    def index():
        return render_template("index.html", posts=_posts)

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/blog/<slug>")
    def blog_post(slug):
        post = next((p for p in _posts if p.get("slug") == slug), None)
        if not post:
            abort(404)
        return render_template("blog_post.html", post=post)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    # API: Sites
    @app.get("/api/v1/sites")
    def api_list_sites():
        return jsonify(list_sites())

    @app.post("/api/v1/sites")
    def api_upsert_site():
        data = request.get_json(force=True, silent=True) or {}
        slug = data.get("slug")
        routes = data.get("routes")
        if not slug:
            return jsonify({"error": "slug is required"}), 400
        if not routes:
            routes = default_site_routes()
        site = upsert_site(slug, routes)
        return jsonify(site), 201

    # API: Jobs
    @app.get("/api/v1/jobs")
    def api_list_jobs():
        limit = int(request.args.get("limit", "50"))
        offset = int(request.args.get("offset", "0"))
        return jsonify(list_jobs(limit=limit, offset=offset))

    @app.get("/api/v1/jobs/<job_id>")
    def api_get_job(job_id):
        job = get_job(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        return jsonify(job)

    @app.post("/api/v1/prerenders")
    def api_trigger_prerender():
        data = request.get_json(force=True, silent=True) or {}
        slug = data.get("site_slug") or data.get("slug") or "site"
        paths = data.get("paths")
        if paths is None:
            site = get_site(slug)
            if not site:
                # Create with default routes if missing
                routes = default_site_routes()
                upsert_site(slug, routes)
                paths = routes
            else:
                paths = site.get("routes") or default_site_routes()
        if not isinstance(paths, list) or not paths:
            return jsonify({"error": "paths must be a non-empty list"}), 400
        job_id = new_job_id()
        create_job(job_id, slug, paths, status="queued")
        # Enqueue
        _job_queue.put({"id": job_id, "site_slug": slug, "paths": paths, "app": app})
        return jsonify({"id": job_id, "status": "queued"}), 202

    # Start background workers once app is ready
    with app.app_context():
        start_workers(app, config.JOB_WORKERS)

    return app



@app.route('/api/render', methods=['POST'])
def _auto_stub_api_render():
    return 'Auto-generated stub for /api/render', 200


@app.route('/cdn/test-page', methods=['GET'])
def _auto_stub_cdn_test_page():
    return 'Auto-generated stub for /cdn/test-page', 200


if __name__ == '__main__':
    pass
