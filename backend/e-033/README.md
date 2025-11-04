# Infrastructure Marketplace API

A Flask-based API for browsing and managing infrastructure templates for common patterns (SaaS, e-commerce, analytics).

## Installation

```bash
pip install -r requirements.txt
```

## Running the App

```bash
python app.py
```

The API will be available at `http://localhost:5000`

## Running Tests

```bash
pytest tests/
```

## API Endpoints

- `GET /` - API information
- `GET /templates` - List all templates
- `GET /templates?category=saas` - Filter templates by category
- `GET /templates/<id>` - Get specific template
- `GET /templates/category/<category>` - Get templates by category
- `POST /templates` - Create new template

## Categories

- `saas` - SaaS infrastructure templates
- `ecommerce` - E-commerce platform templates
- `analytics` - Analytics and data pipeline templates

