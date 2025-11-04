Automated unit / integration / E2E tests generation (pytest, Jest, Playwright)

Stack: Python (Flask), pytest, Jest, Playwright

Quick start
- Python tests
  - pip install -r requirements.txt
  - pytest
- Generate route tests
  - python tools/generate_tests.py
  - pytest tests/generated
- Node tests (Jest + Playwright)
  - npm install
  - npx playwright install --with-deps
  - npm test

E2E tests start a Flask server automatically on http://127.0.0.1:5001 via Playwright webServer.

