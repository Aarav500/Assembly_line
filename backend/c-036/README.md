API Versioning Scaffold and Backward Compatibility Strategies (Flask)

Features:
- URL path versioning: /api/v1/... and /api/v2/...
- Header and query negotiation for unversioned endpoints: /api/...
  - X-API-Version: 1 or v1
  - Accept: application/vnd.example+json; version=2 or application/vnd.example.v2+json
  - Query: ?version=v2 or ?v=2
- Backward compatibility adapters to transform latest canonical models to older schemas and adapt legacy request payloads
- Deprecation signaling: Deprecation, Sunset, Link (rel=deprecation), and Warning 299 headers
- RFC 7807 problem+json error responses

Run:
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python run.py

Test:
- pip install -r requirements.txt
- pytest (if you add pytest) or run tests/test_versioning.py with your preferred runner

Try:
- curl http://localhost:5000/api/v2/users
- curl http://localhost:5000/api/v1/users -i
- curl -H 'Accept: application/vnd.example+json; version=1' http://localhost:5000/api/users -i
- curl -H 'X-API-Version: 2' http://localhost:5000/api/users -i
- curl http://localhost:5000/docs

