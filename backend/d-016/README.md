# CI Job Auto-Splitting Test Suite

Minimal Flask app demonstrating parallel test execution with auto-splitting.

## Features
- Flask API with test splitting endpoint
- GitHub Actions workflow with 4-way parallel test execution
- pytest test suite

## Setup
```bash
pip install -r requirements.txt
python app.py
```

## Run Tests
```bash
pytest tests/ -v
```

## CI Parallelization
Tests automatically split across 4 parallel jobs in GitHub Actions.

