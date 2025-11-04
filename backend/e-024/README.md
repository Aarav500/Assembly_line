# Infrastructure Policy Enforcement via OPA

Minimal Flask application for enforcing infrastructure policies using Open Policy Agent (OPA).

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start OPA server:
```bash
opa run --server --addr localhost:8181 policies/
```

3. Run Flask app:
```bash
python app.py
```

## Run Tests

```bash
pytest tests/
```

## Usage

Validate infrastructure configuration:
```bash
curl -X POST http://localhost:5000/validate \
  -H "Content-Type: application/json" \
  -d '{"resource": "s3_bucket", "encryption": false, "public_access": true}'
```

