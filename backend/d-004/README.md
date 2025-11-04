# Secret Scanner Flask App

A minimal Flask application for scanning secrets with pre-commit enforcement.

## Setup

```bash
pip install -r requirements.txt
pip install pre-commit detect-secrets
pre-commit install
detect-secrets scan > .secrets.baseline
```

## Run

```bash
python app.py
```

## Test

```bash
pytest tests/
```

## API Endpoints

- `GET /` - API info
- `POST /scan` - Scan content for secrets
- `GET /health` - Health check

