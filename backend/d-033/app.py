import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Flask, jsonify, request

from config import config
from utils.crypto import load_signer
from utils.dsse import create_envelope, verify_envelope_with_signer
from utils.storage import get_attestation_path, save_json, load_json
from models import AttestRequest

app = Flask(__name__)

signer = load_signer(
    priv_pem_file=config.PRIV_KEY_PEM_FILE,
    priv_b64=config.PRIV_KEY_B64,
    save_generated_to=config.SAVE_GENERATED_KEY_TO,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.route("/healthz", methods=["GET"])  # readiness/liveness probe
def healthz():
    return jsonify({"ok": True, "time": now_iso(), "keyid": signer.keyid})


@app.route("/api/v1/pubkey", methods=["GET"])  # expose key metadata for verifiers
def pubkey():
    return jsonify({
        "keyid": signer.keyid,
        "publicKey": {
            "format": "ed25519-pem",
            "pem": signer.public_key_pem(),
            "raw_b64url": signer.public_key_b64(),
        },
    })


@app.route("/api/v1/attest", methods=["POST"])  # CI submits build info here
def api_attest():
    try:
        body = request.get_json(force=True)
        req = AttestRequest(**body)
    except Exception as e:
        return jsonify({"ok": False, "error": f"invalid request: {str(e)}"}), 400

    # Construct in-toto Statement v1 with SLSA provenance predicate
    statement = build_in_toto_statement(req)

    envelope = create_envelope(
        signer,
        payload_type="application/vnd.in-toto+json",
        payload_obj=statement,
    )

    path = get_attestation_path(config.STORAGE_DIR, req.build_id)
    save_json(path, envelope)

    return jsonify({
        "ok": True,
        "build_id": req.build_id,
        "keyid": signer.keyid,
        "stored_at": path,
        "envelope": envelope,
    })


@app.route("/api/v1/attestations/<build_id>", methods=["GET"])  # fetch stored envelope
def get_attestation(build_id: str):
    path = get_attestation_path(config.STORAGE_DIR, build_id)
    data = load_json(path)
    if data is None:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "envelope": data})


@app.route("/api/v1/verify", methods=["POST"])  # verify a provided envelope
def api_verify():
    try:
        envelope = request.get_json(force=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"invalid json: {str(e)}"}), 400

    ok, payload = verify_envelope_with_signer(signer, envelope)
    return jsonify({"ok": ok, "payload": payload})


def build_in_toto_statement(req: AttestRequest) -> Dict[str, Any]:
    now = now_iso()
    subjects = [{"name": a.name, "digest": a.digest} for a in req.artifacts]

    predicate = {
        "buildDefinition": {
            "buildType": "https://example.com/build/python-package",
            "externalParameters": {
                "project": req.project,
                "git": req.git.dict(),
            },
            "resolvedDependencies": [],
        },
        "runDetails": {
            "builder": {
                "id": req.builder.id,
            },
            "metadata": {
                "invocationId": req.builder.ci.run_id,
                "startedOn": now,
                "finishedOn": now,
                "buildInvocation": {
                    "ci": req.builder.ci.dict(),
                }
            },
        },
    }

    if req.predicates:
        # Merge custom predicates into predicate map under "custom"
        predicate["custom"] = req.predicates

    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": predicate,
    }
    return statement


if __name__ == "__main__":
    os.makedirs(config.STORAGE_DIR, exist_ok=True)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)



def create_app():
    return app
