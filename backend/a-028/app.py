import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
import shutil
import tempfile
import time
import subprocess
from flask import Flask, request, jsonify

from readiness.scanner import scan_project
from readiness.scoring import compute_scores


def clone_repo(git_url: str) -> str:
    tmpdir = tempfile.mkdtemp(prefix="readiness_")
    try:
        # --depth 1 for efficiency
        subprocess.run([
            "git", "clone", "--depth", "1", git_url, tmpdir
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return tmpdir
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise e


def create_app():
    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def root():
        return jsonify({
            "name": "Project Readiness Scorer",
            "version": "1.0.0",
            "endpoints": {
                "POST /score": {
                    "body": {
                        "path": "local filesystem path to project (optional)",
                        "git_url": "git clone URL (optional)"
                    }
                }
            }
        })

    @app.route("/score", methods=["POST"])
    def score():
        payload = request.get_json(silent=True) or {}
        repo_path = payload.get("path")
        git_url = payload.get("git_url")

        if not repo_path and not git_url:
            return jsonify({"error": "Provide either 'path' or 'git_url'"}), 400

        temp_dir = None
        try:
            if git_url:
                temp_dir = clone_repo(git_url)
                target_path = temp_dir
            else:
                target_path = os.path.abspath(repo_path)
                if not os.path.isdir(target_path):
                    return jsonify({"error": f"Path not found: {target_path}"}), 400

            checks = scan_project(target_path)
            scores = compute_scores(checks)

            result = {
                "project_path": target_path,
                "source": "git" if git_url else "path",
                "computed_at": int(time.time()),
                "overall_score": scores["overall"],
                "category_scores": scores["categories"],
                "checks": checks
            }
            return jsonify(result)
        except subprocess.CalledProcessError as e:
            return jsonify({
                "error": "Failed to clone repository",
                "details": e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
            }), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app = create_app()
    app.run(host="0.0.0.0", port=port)

