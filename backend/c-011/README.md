# Mock Server & Contract Testing

Minimal Flask application demonstrating mock servers and contract testing with Pact and WireMock.

## Setup

```bash
pip install -r requirements.txt
```

## Run Application

```bash
python app.py
```

## Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_app.py
pytest tests/test_contract_pact.py
pytest tests/test_contract_wiremock.py
```

## Endpoints

- `GET /` - API info
- `GET /users` - List all users
- `GET /users/<id>` - Get user by ID
- `POST /users` - Create new user

