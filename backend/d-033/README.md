CI-based security attestations to certify builds (in-toto)

Overview:
- A Flask service that generates and verifies DSSE-signed in-toto statements for CI builds.
- Uses Ed25519 signing keys.

Quick start:
1) Install deps: pip install -r requirements.txt
2) Run dev server: python app.py
3) Attest a build:
   curl -sS -X POST http://localhost:8080/api/v1/attest \
     -H 'content-type: application/json' \
     -d '{
       "build_id":"build-123",
       "project":"example/proj",
       "git":{"commit":"abc123","ref":"refs/heads/main","repo":"https://github.com/example/proj"},
       "builder":{"id":"urn:ci:github-actions","ci":{"name":"github-actions","run_id":"12345","url":"https://github.com/.../runs/12345"}},
       "artifacts":[{"name":"dist/pkg-1.0.0.tar.gz","digest":{"sha256":"deadbeef..."},"uri":"https://example.com/dist/pkg-1.0.0.tar.gz"}]}' | jq .

Environment variables:
- ATTESTATION_STORAGE_DIR: directory to store envelopes (default: ./attestations)
- ATTESTATION_PRIVATE_KEY_PEM_FILE: path to Ed25519 private key (PEM, PKCS#8)
- ATTESTATION_PRIVATE_KEY_B64: base64-encoded 32-byte raw Ed25519 private key seed
- ATTESTATION_SAVE_GENERATED_KEY_TO: path to write a newly generated PEM key (dev/testing)

Endpoints:
- GET  /healthz
- GET  /api/v1/pubkey            -> returns keyid and public key
- POST /api/v1/attest            -> create DSSE envelope for provided build info
- POST /api/v1/verify            -> verify a DSSE envelope using server public key
- GET  /api/v1/attestations/:id  -> fetch stored envelope by build_id

Notes:
- This service produces in-toto Statement v1 payloads with predicateType set to SLSA provenance v1.
- DSSE signing uses Ed25519 and DSSEv1 PAE.
- For production, manage keys securely (HSM/KMS) and restrict access.

