Fine-tuning pipelines for open-source LLMs with dataset versioning.

API endpoints:
- GET /health
- GET /datasets
- POST /datasets (multipart: name, files[], metadata?)
- GET /datasets/<name>
- POST /datasets/<name>/versions (multipart: files[], metadata?)
- GET /datasets/<name>/versions/<version>
- GET /datasets/<name>/versions/<version>/download
- POST /train (JSON: model_name, dataset_name, dataset_version=latest, training params)
- GET /jobs
- GET /jobs/<job_id>
- GET /jobs/<job_id>/logs
- POST /jobs/<job_id>/cancel

Quickstart:
1) python3 -m venv .venv && source .venv/bin/activate
2) pip install -r requirements.txt
3) python app.py
4) Create dataset: curl -F "name=myds" -F "files=@sample_data/sample.jsonl" http://localhost:8000/datasets
5) Start training: curl -H "Content-Type: application/json" -d '{"model_name":"gpt2","dataset_name":"myds","num_train_epochs":1}' http://localhost:8000/train

