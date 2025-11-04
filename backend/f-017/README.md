# Flask Load Testing CI Project

Minimal Flask application with integrated CI load/performance testing workflows.

## Features

- Simple Flask REST API
- Unit tests with pytest
- Load testing with Locust
- Performance testing with k6
- GitHub Actions CI pipeline
- Automated test result artifacts

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py

# Run tests
pytest tests/

# Run Locust locally
locust -f locustfile.py --host=http://localhost:5000

# Run k6 locally
k6 run k6-script.js
```

## CI Pipeline

The GitHub Actions workflow includes:
1. Unit tests
2. Locust load testing (generates HTML report and CSV results)
3. k6 performance testing (generates JSON results)

All test results are uploaded as artifacts for review.
