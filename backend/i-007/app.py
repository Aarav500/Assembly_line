import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from slsa.keys import ensure_keypair, load_private_key, load_public_key_bytes, keyid_from_public
from slsa.dsse import sign_envelope, verify_envelope
from slsa.attestation import make_provenance_statement, canonicalize_json

app = Flask(__name__)

KEY_PATH = os.environ.get("ATTESTATION_PRIVATE_KEY", "data/keys/ed25519_private.pem")
BUILDER_ID = os.environ.get("SLSA_BUILDER_ID", "urn:builder:local:slsa-attestation-service")
SERVICE_VERSION = os.environ.get("SERVICE_VERSION", "0.1.0")

os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
ensure_keypair(KEY_PATH)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/keys/public")
def get_public_key():
    pub = load_public_key_bytes(KEY_PATH)
    kid = keyid_from_public(pub)
    return {
        "keyid": kid,
        "publicKey": {
            "raw": pub.hex(),
            "algorithm": "ed25519"
        }
    }

@app.post("/attestations/provenance")
def generate_provenance():
    try:
        req = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    if not isinstance(req, dict):
        return jsonify({"error": "body must be a JSON object"}), 400

    # Required fields validation
    subjects = req.get("subject")
    if not isinstance(subjects, list) or not subjects:
        return jsonify({"error": "subject must be a non-empty list"}), 400

    for s in subjects:
        if not isinstance(s, dict) or "name" not in s or "digest" not in s:
            return jsonify({"error": "each subject must have name and digest"}), 400
        if "sha256" not in s["digest"]:
            return jsonify({"error": "subject.digest must include sha256"}), 400

    build_type = req.get("buildType")
    if not isinstance(build_type, str) or not build_type:
        return jsonify({"error": "buildType is required (string)"}), 400

    external_parameters = req.get("externalParameters", {})
    internal_parameters = req.get("internalParameters")
    resolved_dependencies = req.get("resolvedDependencies", [])

    invocation_id = req.get("invocationId")
    started_on = req.get("startedOn")
    finished_on = req.get("finishedOn")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not started_on:
        started_on = now
    if not finished_on:
        finished_on = now

    builder_version = {"attestation-service": SERVICE_VERSION}

    statement = make_provenance_statement(
        subjects=subjects,
        build_type=build_type,
        external_parameters=external_parameters,
        internal_parameters=internal_parameters,
        resolved_dependencies=resolved_dependencies,
        builder_id=BUILDER_ID,
        builder_version=builder_version,
        invocation_id=invocation_id,
        started_on=started_on,
        finished_on=finished_on,
    )

    payload_bytes = canonicalize_json(statement)

    priv = load_private_key(KEY_PATH)
    pub_bytes = load_public_key_bytes(KEY_PATH)
    kid = keyid_from_public(pub_bytes)

    envelope = sign_envelope(
        payload_type="application/vnd.in-toto+json",
        payload_bytes=payload_bytes,
        private_key=priv,
        keyid=kid,
    )

    return jsonify(envelope)

@app.post("/attestations/verify")
def verify():
    try:
        req = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    if not isinstance(req, dict):
        return jsonify({"error": "body must be a JSON object"}), 400

    envelope = req.get("envelope")
    if not isinstance(envelope, dict):
        return jsonify({"error": "envelope is required"}), 400

    artifact = req.get("artifact")
    if artifact and (not isinstance(artifact, dict) or "digest" not in artifact or "sha256" not in artifact["digest"]):
        return jsonify({"error": "artifact must include digest.sha256 if provided"}), 400

    pub = load_public_key_bytes(KEY_PATH)
    kid = keyid_from_public(pub)
    try:
        payload_bytes = verify_envelope(envelope, {kid: pub})
    except Exception as e:
        return jsonify({"verified": False, "error": str(e)}), 400

    try:
        payload = json.loads(payload_bytes)
    except Exception:
        return jsonify({"verified": False, "error": "payload is not valid JSON"}), 400

    if payload.get("predicateType") != "https://slsa.dev/provenance/v1" and payload.get("predicateType") != "https://slsa.dev/provenance/v1.0":
        return jsonify({"verified": False, "error": "predicateType is not SLSA v1"}), 400

    if artifact:
        subjects = payload.get("subject", [])
        match = any(
            isinstance(s, dict)
            and s.get("digest", {}).get("sha256") == artifact["digest"]["sha256"]
            for s in subjects
        )
        if not match:
            return jsonify({"verified": False, "error": "subject digest does not match artifact"}), 400

    return jsonify({"verified": True, "keyid": kid, "payload": payload})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))



def create_app():
    return app


@app.route('/generate-attestation', methods=['POST'])
def _auto_stub_generate_attestation():
    return 'Auto-generated stub for /generate-attestation', 200
