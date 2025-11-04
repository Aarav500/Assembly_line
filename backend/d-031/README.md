# Compliance Checks CI

A Flask API for running GDPR and HIPAA compliance checks as CI jobs.

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

## Testing

```bash
pytest tests/
```

## API Endpoints

- `GET /` - API info
- `GET /compliance/<standard>` - Get compliance checks for a standard (gdpr/hipaa)
- `POST /compliance/<standard>/check` - Run compliance check
- `GET /compliance/all` - List all standards

## CI/CD

The GitHub Actions workflow runs GDPR and HIPAA compliance checks on every push and pull request.

