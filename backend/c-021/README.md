Background job & queue scaffolding (Flask + Celery + RQ)

Quickstart
- Copy .env.example to .env and adjust as needed
- docker-compose up --build
- Web API: http://localhost:5000/api
- Flower (Celery monitor): http://localhost:5555/flower

Example API calls
- Celery add: POST http://localhost:5000/api/tasks/celery/add with JSON {"a": 1, "b": 2}
- Celery long: POST http://localhost:5000/api/tasks/celery/long with JSON {"duration": 5}
- Celery status: GET http://localhost:5000/api/tasks/celery/<task_id>
- RQ add: POST http://localhost:5000/api/tasks/rq/add with JSON {"a": 1, "b": 2}
- RQ long: POST http://localhost:5000/api/tasks/rq/long with JSON {"duration": 5}
- RQ status: GET http://localhost:5000/api/tasks/rq/<job_id>

Notes
- Sidekiq bridge: Minimal Redis enqueuer provided at POST /api/bridge/sidekiq/enqueue. Requires external Ruby Sidekiq worker with the referenced class.
- Bull: Not implemented due to protocol complexity; use Node/Bull producer/worker.

