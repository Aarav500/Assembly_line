# Flask CI/CD Demo

Minimal Flask application with GitHub Actions CI/CD pipeline.

## Features

- Flask REST API
- Automated testing with pytest
- GitHub Actions workflows for lint, test, build, and deploy

## Setup

```bash
pip install -r requirements.txt
python app.py
```

## Run Tests

```bash
pytest tests/
```

## CI/CD Pipeline

The GitHub Actions workflow includes:
- **Lint**: Code quality checks with flake8
- **Test**: Automated testing with pytest
- **Build**: Application build verification
- **Deploy**: Automated deployment on main branch
