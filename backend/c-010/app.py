import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import glob
from flask import Flask, request, jsonify, send_from_directory, render_template
from pathlib import Path
from typing import Optional, Dict, Any

from config import STORAGE, DEFAULT_VIEWPORT, DEFAULT_THRESHOLD
from utils import ensure_storage, timestamp_str, safe_name, save_json, load_json, list_sorted_by_mtime
from snapshotter import Snapshotter
from comparer import compare_images

app = Flask(__name__)

# Ensure storage directories exist
ensure_storage()


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/api/snapshot", methods=["POST"]) 
def api_snapshot():
    payload = request.get_json(force=True, silent=True) or {}
    url = payload.get("url")
    if not url:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    name = safe_name(payload.get("name") or payload.get("test") or "snapshot")
    viewport = payload.get("viewport") or {}
    width = int(viewport.get("width") or DEFAULT_VIEWPORT["width"])
    height = int(viewport.get("height") or DEFAULT_VIEWPORT["height"])

    full_page = bool(payload.get("full_page", True))
    selector = payload.get("selector")
    wait_until = payload.get("wait_until", "networkidle")
    timeout_ms = int(payload.get("timeout_ms", 30000))
    delay_ms = int(payload.get("delay_ms", 0))
    device_scale_factor = float(payload.get("device_scale_factor", 1))
    emulate_media = payload.get("emulate_media")

    ts = timestamp_str()
    filename = f"{ts}__{name}.png"
    out_path = STORAGE["snapshots"] / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    snapper = Snapshotter()
    try:
        meta = snapper.capture(
            url=url,
            out_path=str(out_path),
            width=width,
            height=height,
            full_page=full_page,
            selector=selector,
            wait_until=wait_until,
            timeout_ms=timeout_ms,
            delay_ms=delay_ms,
            device_scale_factor=device_scale_factor,
            emulate_media=emulate_media,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Save metadata file
    meta_path = STORAGE["results"] / f"{ts}__{name}__snapshot.json"
    save_json(meta_path, {
        "type": "snapshot",
        "name": name,
        "timestamp": ts,
        "url": url,
        "snapshot_path": str(out_path),
        "viewport": {"width": width, "height": height},
        "full_page": full_page,
        "selector": selector,
        "playwright": meta,
    })

    return jsonify({
        "ok": True,
        "name": name,
        "timestamp": ts,
        "snapshot_path": str(out_path),
        "meta": meta,
    })


@app.route("/api/baseline/promote", methods=["POST"]) 
def api_promote_baseline():
    payload = request.get_json(force=True, silent=True) or {}
    name = safe_name(payload.get("name") or payload.get("test") or "snapshot")
    snapshot_path = payload.get("snapshot_path")

    if not snapshot_path:
        # find latest snapshot for this name
        pattern = str(STORAGE["snapshots"] / f"*__{name}.png")
        files = sorted(glob.glob(pattern))
        if not files:
            return jsonify({"error": f"No snapshots found for name '{name}'"}), 404
        snapshot_path = files[-1]

    snapshot_path = Path(snapshot_path)
    if not snapshot_path.exists():
        return jsonify({"error": f"Snapshot path not found: {snapshot_path}"}), 404

    baseline_path = STORAGE["baselines"] / f"{name}.png"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy file
    data = snapshot_path.read_bytes()
    baseline_path.write_bytes(data)

    ts = timestamp_str()
    meta_path = STORAGE["results"] / f"{ts}__{name}__baseline.json"
    save_json(meta_path, {
        "type": "baseline_promote",
        "name": name,
        "timestamp": ts,
        "baseline_path": str(baseline_path),
        "source_snapshot": str(snapshot_path),
    })

    return jsonify({
        "ok": True,
        "name": name,
        "baseline_path": str(baseline_path),
        "source_snapshot": str(snapshot_path),
    })


@app.route("/api/compare", methods=["POST"]) 
def api_compare():
    payload = request.get_json(force=True, silent=True) or {}
    name = safe_name(payload.get("name") or payload.get("test") or "snapshot")

    baseline_path = payload.get("baseline_path") or str(STORAGE["baselines"] / f"{name}.png")
    candidate_path = payload.get("candidate_path")
    threshold = float(payload.get("threshold", DEFAULT_THRESHOLD))

    if not candidate_path:
        # find latest snapshot for this name
        pattern = str(STORAGE["snapshots"] / f"*__{name}.png")
        files = sorted(glob.glob(pattern))
        if not files:
            return jsonify({"error": f"No snapshots found for name '{name}'"}), 404
        candidate_path = files[-1]

    baseline_path = Path(baseline_path)
    candidate_path = Path(candidate_path)

    if not baseline_path.exists():
        return jsonify({
            "error": f"Baseline not found for name '{name}'", 
            "baseline_missing": True,
            "baseline_path": str(baseline_path)
        }), 404

    if not candidate_path.exists():
        return jsonify({"error": f"Candidate snapshot not found: {candidate_path}"}), 404

    ts = timestamp_str()
    diff_path = STORAGE["diffs"] / f"{ts}__{name}__diff.png"
    diff_path.parent.mkdir(parents=True, exist_ok=True)

    result = compare_images(
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        diff_path=str(diff_path),
        threshold_percent=threshold,
    )

    result_record = {
        "type": "comparison",
        "name": name,
        "timestamp": ts,
        "baseline_path": str(baseline_path),
        "candidate_path": str(candidate_path),
        "diff_path": str(diff_path),
        **result,
    }

    result_json_path = STORAGE["results"] / f"{ts}__{name}__compare.json"
    save_json(result_json_path, result_record)

    return jsonify({"ok": True, **result_record})


@app.route("/api/results/<name>", methods=["GET"]) 
def api_results_for_name(name: str):
    name = safe_name(name)
    pattern = str(STORAGE["results"] / f"*__{name}__compare.json")
    files = list_sorted_by_mtime(pattern)
    results = [load_json(Path(p)) for p in files]
    return jsonify({
        "name": name,
        "count": len(results),
        "results": results,
    })


@app.route("/api/list", methods=["GET"]) 
def api_list():
    baselines = sorted([str(p) for p in STORAGE["baselines"].glob("*.png")])
    snapshots = list_sorted_by_mtime(str(STORAGE["snapshots"] / "*.png"))
    diffs = list_sorted_by_mtime(str(STORAGE["diffs"] / "*.png"))
    results = list_sorted_by_mtime(str(STORAGE["results"] / "*.json"))
    return jsonify({
        "baselines": baselines,
        "snapshots": snapshots,
        "diffs": diffs,
        "results": results,
    })


@app.route("/report", methods=["GET"]) 
def report():
    # Build a simple report of latest comparison per test name
    pattern = str(STORAGE["results"] / "*__*__compare.json")
    files = list_sorted_by_mtime(pattern)
    latest_by_name: Dict[str, Dict[str, Any]] = {}
    for p in files:
        rec = load_json(Path(p))
        name = rec.get("name")
        # overwrite to keep latest since files sorted asc
        latest_by_name[name] = rec

    items = sorted(latest_by_name.values(), key=lambda r: r.get("name"))
    return render_template("report.html", items=items)


@app.route('/storage/<path:filename>') 
def serve_storage(filename):
    # allow serving images in storage for the report
    base = Path("storage").resolve()
    file_path = (base / filename).resolve()
    if not str(file_path).startswith(str(base)):
        return "Forbidden", 403
    directory = file_path.parent
    return send_from_directory(directory, file_path.name)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)



def create_app():
    return app


@app.route('/about', methods=['GET'])
def _auto_stub_about():
    return 'Auto-generated stub for /about', 200


@app.route('/api/data', methods=['GET'])
def _auto_stub_api_data():
    return 'Auto-generated stub for /api/data', 200
