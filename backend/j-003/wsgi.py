from app import create_app

app = create_app()

# Gunicorn entry: gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

