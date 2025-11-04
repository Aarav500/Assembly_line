Onboarding Checklist Generator (Flask)

Overview
- Auto-generate onboarding checklists for new hires per project.
- Define project-specific task templates with due-date offsets and optional role filters.
- Create a new hire, assign them to a project and start date; their checklist is generated automatically.

Quickstart
1) Create and activate a virtual environment (optional)
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

2) Install dependencies
   pip install -r requirements.txt

3) Run the app
   python app.py

4) Open in browser
   http://127.0.0.1:5000/

Notes
- Uses SQLite by default (onboarding.db). Override with DATABASE_URL environment variable.
- The initial run seeds a sample project, task templates, and a sample hire.
- "Update from Templates" on an employee page adds any new template tasks that weren’t previously generated.

