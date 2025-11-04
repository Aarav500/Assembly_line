# Local dev environments & Codespaces templates auto-generated per project

This repository demonstrates a Python + Flask app with auto-generated local dev environment and GitHub Codespaces templates.

Quick start:
- Local: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt && python run.py`
- Dev Container / Codespaces: Open in Codespaces or Dev Containers; dependencies install automatically. Use the provided VS Code launch configurations.

Regenerate dev environment templates:
- Edit `project.config.json` and run `python scripts/generate_dev_env.py`.
- A GitHub Action also regenerates on push to main.

