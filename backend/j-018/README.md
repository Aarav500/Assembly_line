Accessibility tooling integrated into dev workflow and UI suggestions

Overview:
- Flask web app to analyze HTML for accessibility issues.
- CLI tool for integrating into CI/CD and pre-commit.
- Common checks: missing alt text, missing form labels, accessible names for links/buttons, heading structure, landmarks, tabindex misuse, title-only usage, and inline color contrast AA checks.

Quick start:
1) Install dependencies:
   pip install -r requirements.txt

2) Run the web app:
   python app.py
   Open http://localhost:5000

3) Run the CLI on templates directory:
   python cli.py templates

Pre-commit:
- Install pre-commit and set up hooks:
  pip install pre-commit
  pre-commit install

Notes:
- Color contrast analysis only considers inline styles and assumes white background when unknown. It is an approximation.
- Template engines (e.g., Jinja) may include placeholders the parser ignores.
- This tool is a lightweight static analyzer; for full coverage consider complementing with end-to-end tooling like axe in browser tests.

