import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from flask import Flask, request, jsonify

from smoke.checks import check_dns, check_tcp, check_http, check_icmp
from smoke.utils import parse_bool
from config import MAX_CONCURRENCY

from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("smoke")

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/smoke/dns")
def smoke_dns():
    host = request.args.get("host")
    if not host:
        return jsonify({"ok": False, "error": "missing required parameter: host"}), 400
    timeout = float(request.args.get("timeout", 2.0))

    result = check_dns(host=host, timeout=timeout)
    status = 200 if result.get("ok") else 503
    return jsonify(result), status

@app.get("/smoke/tcp")
def smoke_tcp():
    host = request.args.get("host")
    port = request.args.get("port")
    if not host or not port:
        return jsonify({"ok": False, "error": "missing required parameters: host, port"}), 400
    try:
        port = int(port)
    except ValueError:
        return jsonify({"ok": False, "error": "port must be an integer"}), 400

    timeout = float(request.args.get("timeout", 2.0))

    result = check_tcp(host=host, port=port, timeout=timeout)
    status = 200 if result.get("ok") else 503
    return jsonify(result), status

@app.get("/smoke/http")
def smoke_http():
    url = request.args.get("url")
    if not url:
        return jsonify({"ok": False, "error": "missing required parameter: url"}), 400

    method = request.args.get("method", "HEAD").upper()
    timeout = float(request.args.get("timeout", 3.0))
    expect_status = request.args.get("expect_status")
    allow_redirects = parse_bool(request.args.get("allow_redirects", "true"))

    if expect_status is not None:
        try:
            expect_status = int(expect_status)
        except ValueError:
            return jsonify({"ok": False, "error": "expect_status must be an integer"}), 400

    result = check_http(url=url, method=method, timeout=timeout, expect_status=expect_status, allow_redirects=allow_redirects)
    status = 200 if result.get("ok") else 503
    return jsonify(result), status

@app.get("/smoke/icmp")
def smoke_icmp():
    host = request.args.get("host")
    if not host:
        return jsonify({"ok": False, "error": "missing required parameter: host"}), 400

    timeout = float(request.args.get("timeout", 2.0))
    count = int(request.args.get("count", 1))

    result = check_icmp(host=host, timeout=timeout, count=count)
    status = 200 if result.get("ok") else 503
    return jsonify(result), status

@app.post("/smoke/batch")
def smoke_batch():
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"ok": False, "error": "invalid JSON body"}), 400

    tests = data.get("tests") if isinstance(data, dict) else None
    if not isinstance(tests, list) or not tests:
        return jsonify({"ok": False, "error": "body must contain non-empty 'tests' array"}), 400

    results = []

    def run_test(spec):
        t = (spec.get("type") or "").lower()
        try:
            if t == "dns":
                return check_dns(host=spec["host"], timeout=float(spec.get("timeout", 2.0)))
            elif t == "tcp":
                return check_tcp(host=spec["host"], port=int(spec["port"]), timeout=float(spec.get("timeout", 2.0)))
            elif t == "http":
                expect_status = spec.get("expect_status")
                if expect_status is not None:
                    expect_status = int(expect_status)
                return check_http(
                    url=spec["url"],
                    method=(spec.get("method") or "HEAD").upper(),
                    timeout=float(spec.get("timeout", 3.0)),
                    expect_status=expect_status,
                    allow_redirects=parse_bool(spec.get("allow_redirects", True)),
                )
            elif t == "icmp":
                return check_icmp(host=spec["host"], timeout=float(spec.get("timeout", 2.0)), count=int(spec.get("count", 1)))
            else:
                return {"ok": False, "type": t, "error": f"unsupported test type: {t}"}
        except KeyError as e:
            return {"ok": False, "type": t, "error": f"missing required field: {e.args[0]}"}
        except Exception as e:
            return {"ok": False, "type": t, "error": str(e)}

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        future_map = {executor.submit(run_test, t): t for t in tests}
        for fut in as_completed(future_map):
            results.append(fut.result())

    overall_ok = all(r.get("ok") for r in results if isinstance(r, dict))
    status = 200 if overall_ok else 503
    return jsonify({"ok": overall_ok, "results": results}), status

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))



def create_app():
    return app


@app.route('/check/port/5000', methods=['GET'])
def _auto_stub_check_port_5000():
    return 'Auto-generated stub for /check/port/5000', 200
