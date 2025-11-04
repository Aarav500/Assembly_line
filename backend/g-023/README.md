Experiment Tracker Integration Service (Flask)

Endpoints:
- GET /health
- POST /train

POST /train payload example:
{
  "tracker": "mlflow",  // or "wandb" or "none"
  "experiment_name": "demo-flask-tracker",
  "run_name": "try-1",
  "params": {"C": 0.5, "max_iter": 300},
  "test_size": 0.2,
  "random_state": 42,
  "log_artifacts": true
}

Environment variables (see .env.example) control MLflow and W&B configuration.

Run locally:
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- export FLASK_APP=app.py
- python app.py

Docker:
- docker build -t tracker-app .
- docker run --rm -p 8000:8000 --env-file .env tracker-app

