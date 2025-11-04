# Flask API with Auto-Generated Documentation

A minimal Flask application with Swagger UI and MkDocs documentation.

## Features

- Flask REST API
- Swagger UI at `/api/docs`
- MkDocs documentation site
- GitHub Pages deployment
- pytest tests

## Setup

```bash
pip install -r requirements.txt
python app.py
```

## Documentation

- **Swagger UI**: http://localhost:5000/api/docs
- **MkDocs**: Run `mkdocs serve` and visit http://localhost:8000
- **GitHub Pages**: Automatically deployed on push to main

## Testing

```bash
pytest tests/
```

## Deploy Docs to GitHub Pages

```bash
mkdocs gh-deploy
```

