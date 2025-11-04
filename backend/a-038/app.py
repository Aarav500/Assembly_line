import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from risk_scoring import (
    score_technical_debt,
    score_backups,
    score_ci,
    score_dependencies,
    aggregate_scores,
    grade_from_score,
)
from deps_checker import parse_requirements_text, fetch_latest_versions, analyze_outdated


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return jsonify({
            "name": "Project Risk Scoring API",
            "version": "1.0.0",
            "endpoints": {
                "POST /api/dependencies/outdated": {
                    "desc": "Check outdated Python libs from requirements text or explicit package list",
                    "body": {
                        "dependencies": {
                            "requirements": "name==version\n...",  # optional
                            "packages": [{"name": "flask", "version": "2.0.0"}]  # optional
                        }
                    }
                },
                "POST /api/score": {
                    "desc": "Compute overall project risk score",
                    "body": {
                        "technical_debt": {
                            "debt_score": 0,
                            "linter_issues": 0,
                            "todo_count": 0,
                            "test_coverage": 80.0,
                            "complexity": 10.0
                        },
                        "dependencies": {
                            "requirements": "name==version\n...",
                            "packages": [{"name": "flask", "version": "2.0.0"}]
                        },
                        "backups": {
                            "has_backups": True,
                            "last_backup_days": 1,
                            "tested_restore": True
                        },
                        "ci": {
                            "has_ci": True,
                            "status": "passing",
                            "last_build_days": 1
                        }
                    }
                }
            }
        })

    @app.route("/api/dependencies/outdated", methods=["POST"])
    def api_outdated():
        try:
            payload = request.get_json(force=True, silent=False) or {}
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

        deps = (payload or {}).get("dependencies", {})
        requirements_text = deps.get("requirements")
        packages = deps.get("packages") or []

        parsed_packages = []
        if requirements_text:
            parsed_packages.extend(parse_requirements_text(requirements_text))
        if isinstance(packages, list):
            for p in packages:
                name = (p or {}).get("name")
                version = (p or {}).get("version")
                if name and version:
                    parsed_packages.append({"name": name, "version": str(version)})

        if not parsed_packages:
            return jsonify({"error": "No packages provided. Provide dependencies.requirements or dependencies.packages."}), 400

        timeout = float(os.getenv("PYPI_TIMEOUT", "5"))
        latest_map, errors = fetch_latest_versions(parsed_packages, timeout=timeout)
        analysis = analyze_outdated(parsed_packages, latest_map)

        return jsonify({
            "packages": analysis,
            "errors": errors,
        })

    @app.route("/api/score", methods=["POST"])
    def api_score():
        try:
            payload = request.get_json(force=True, silent=False) or {}
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

        # Technical debt
        tech = (payload or {}).get("technical_debt", {})
        tech_score, tech_details = score_technical_debt(tech)

        # Dependencies
        deps = (payload or {}).get("dependencies", {})
        requirements_text = deps.get("requirements")
        packages = deps.get("packages") or []
        parsed_packages = []
        if requirements_text:
            parsed_packages.extend(parse_requirements_text(requirements_text))
        if isinstance(packages, list):
            for p in packages:
                name = (p or {}).get("name")
                version = (p or {}).get("version")
                if name and version:
                    parsed_packages.append({"name": name, "version": str(version)})

        dep_details = {
            "packages": [],
            "errors": {},
            "present": bool(parsed_packages)
        }
        dep_score = None
        if parsed_packages:
            timeout = float(os.getenv("PYPI_TIMEOUT", "5"))
            latest_map, errors = fetch_latest_versions(parsed_packages, timeout=timeout)
            analysis = analyze_outdated(parsed_packages, latest_map)
            dep_score, dep_calc = score_dependencies(analysis)
            dep_details.update({
                "packages": analysis,
                "errors": errors,
                "calc": dep_calc,
            })

        # Backups
        backups = (payload or {}).get("backups", {})
        backup_score, backup_details = score_backups(backups)

        # CI
        ci = (payload or {}).get("ci", {})
        ci_score, ci_details = score_ci(ci)

        component_scores = {
            "technical_debt": tech_score,
            "dependencies": dep_score,
            "backups": backup_score,
            "ci": ci_score,
        }
        details = {
            "technical_debt": tech_details,
            "dependencies": dep_details,
            "backups": backup_details,
            "ci": ci_details,
        }

        overall_score, weight_info = aggregate_scores(component_scores)
        details["weights"] = weight_info

        return jsonify({
            "score": round(overall_score, 2) if overall_score is not None else None,
            "grade": grade_from_score(overall_score) if overall_score is not None else None,
            "components": component_scores,
            "details": details,
        })

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app = create_app()
    app.run(host="0.0.0.0", port=port)

