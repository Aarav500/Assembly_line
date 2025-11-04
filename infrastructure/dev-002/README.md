Pre-commit hooks with Ruff/Black, Mypy, and fast Pytest

- Install dev tools: pip install -r requirements-dev.txt
- Install hooks: pre-commit install --install-hooks
- Commit flow will run: ruff, black, mypy, and fast tests (excluding tests marked slow)

Local commands:
- make format
- make lint
- make typecheck
- make test

