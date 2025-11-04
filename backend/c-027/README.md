# Flask i18n Project

## Setup

```bash
pip install -r requirements.txt
```

## Compile translations

```bash
pybabel compile -d translations
```

## Run

```bash
python app.py
```

## Test

```bash
pytest
```

## Usage

- Default (English): http://localhost:5000/
- Spanish: http://localhost:5000/?lang=es
- French: http://localhost:5000/?lang=fr

