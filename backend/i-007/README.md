SLSA / in-toto attestation generation for release provenance (Python/Flask)

Endpoints:
- GET /healthz: Health check
- GET /keys/public: Returns current Ed25519 public key and keyid (SHA256 hex of raw public key)
- POST /attestations/provenance: Generates an in-toto Statement with SLSA v1 provenance predicate, wrapped in a DSSE envelope and signed with the service key.
- POST /attestations/verify: Verifies a DSSE envelope using the service public key and optionally checks the subject digest against a provided artifact.

Running:
1) pip install -r requirements.txt
2) python app.py

Configuration (env):
- ATTESTATION_PRIVATE_KEY: Path to PEM-encoded Ed25519 private key (default: data/keys/ed25519_private.pem). If missing, a new key is generated on first run.
- SLSA_BUILDER_ID: Builder identity URI (default: urn:builder:local:slsa-attestation-service)
- SERVICE_VERSION: Service version string added to builder.version (default: 0.1.0)

Example: Generate provenance
curl -sS -X POST http://localhost:8080/attestations/provenance \
  -H 'Content-Type: application/json' \
  -d '{
    "subject": [{"name": "myapp-1.2.3.tgz", "digest": {"sha256": "aabbcc..."}}],
    "buildType": "https://slsa-framework.github.io/github-actions-buildtypes/workflow/v1",
    "externalParameters": {"release_tag": "v1.2.3"},
    "resolvedDependencies": [{"uri": "git+https://github.com/org/repo@deadbeef", "digest": {"sha1": "deadbeef"}, "name": "source"}],
    "invocationId": "build-123"
  }'

Example: Verify envelope
curl -sS -X POST http://localhost:8080/attestations/verify \
  -H 'Content-Type: application/json' \
  -d '{
    "envelope": {"payloadType": "application/vnd.in-toto+json", "payload": "...", "signatures": [{"keyid": "...", "sig": "..."}]},
    "artifact": {"name": "myapp-1.2.3.tgz", "digest": {"sha256": "aabbcc..."}}
  }'

