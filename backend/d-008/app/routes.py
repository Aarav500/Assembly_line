import os
import time
from flask import Blueprint, current_app, jsonify, request
from .scanners.trivy_scanner import TrivyScanner
from .scanners.snyk_scanner import SnykScanner
from .utils import normalize_trivy, normalize_snyk, safe_bool
from .mitigation import generate_mitigations

bp = Blueprint("routes", __name__)


@bp.route("/healthz", methods=["GET"])  # k8s probe friendly
def healthz():
    return jsonify({"status": "ok"})


@bp.route("/scan", methods=["POST"])  # primary API: run scans and get suggestions
def scan():
    payload = request.get_json(silent=True) or {}

    target = payload.get("target")
    target_type = (payload.get("target_type") or "fs").lower()  # fs | image
    tools = payload.get("tools") or ["trivy", "snyk"]
    options = payload.get("options") or {}

    if target_type not in ("fs", "image"):
        return jsonify({"error": "target_type must be 'fs' or 'image'"}), 400

    if not target:
        return jsonify({"error": "target is required"}), 400

    # Optional filters
    severity = options.get("severity")  # e.g., "HIGH,CRITICAL"
    include_config_scan = safe_bool(options.get("include_config_scan", True)) if target_type == "fs" else False

    # Initialize scanners
    trivy = TrivyScanner(
        trivy_path=current_app.config["TRIVY_PATH"],
        timeout=current_app.config["SCAN_TIMEOUT"],
    )
    snyk = SnykScanner(
        snyk_path=current_app.config["SNYK_PATH"],
        snyk_token=current_app.config.get("SNYK_TOKEN"),
        timeout=current_app.config["SCAN_TIMEOUT"],
    )

    meta = {
        "requestedAt": int(time.time()),
        "target": target,
        "targetType": target_type,
        "tools": tools,
        "options": options,
    }

    results = {}
    errors = {}

    # Run Trivy
    if "trivy" in [t.lower() for t in tools]:
        try:
            if target_type == "image":
                trivy_res = trivy.scan_image(target, severity=severity)
            else:
                trivy_res = trivy.scan_filesystem(
                    target,
                    severity=severity,
                    include_config_scan=include_config_scan,
                )
            results["trivy"] = trivy_res
        except Exception as e:
            errors["trivy"] = str(e)

    # Run Snyk
    if "snyk" in [t.lower() for t in tools]:
        try:
            if target_type == "image":
                snyk_res = snyk.scan_image(target)
            else:
                snyk_res = snyk.scan_filesystem(target)
            results["snyk"] = snyk_res
        except Exception as e:
            errors["snyk"] = str(e)

    # Normalize findings across tools
    normalized = []
    if "trivy" in results:
        normalized.extend(normalize_trivy(results["trivy"]))
    if "snyk" in results:
        normalized.extend(normalize_snyk(results["snyk"]))

    # Generate mitigation suggestions
    mitigations = generate_mitigations(
        normalized_findings=normalized,
        target_type=target_type,
    )

    response = {
        "meta": meta,
        "results": results,
        "normalizedFindings": normalized,
        "mitigations": mitigations,
    }

    if errors:
        response["errors"] = errors

    return jsonify(response)

