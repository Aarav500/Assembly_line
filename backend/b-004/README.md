Idea Templating Library (Flask)

Quickstart
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py
- Open http://localhost:5000

API
- GET /api/categories -> { categories: [{ name, count }] }
- GET /api/templates?category=&q= -> { templates: [summary...] }
- GET /api/templates/:id -> { template }
- POST /api/render { template_id, inputs, format: "markdown"|"plain" } -> { sections, combined, meta }

Environment
- IDEA_LIBRARY_PATH: override path to data/templates.json

Notes
- Templates use Jinja expressions. Available filters: slugify, titlecase, money.
- Base context includes now, today, year.

