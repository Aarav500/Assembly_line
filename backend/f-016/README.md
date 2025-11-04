Automated log-based test-case generation for flaky test detection

Run:
- pip install -r requirements.txt
- python app.py

Endpoints:
- POST /api/logs: Upload logs (multipart 'file'), JSON {'text': '...'}, or {'path': '/dir'}
- GET /api/tests: Aggregated tests
- GET /api/tests/flaky: Flaky tests
- POST /api/generate: Generate tests into ./generated_tests

Generated tests:
- Located in generated_tests/
- Each test verifies flakiness offline using recorded logs
- Set RUN_REPRODUCTION=1 to attempt reproduction by re-running the recorded command(s) with captured seeds

