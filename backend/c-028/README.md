Accessibility-first UI generation (Flask)

Features
- Semantic landmarks: header, nav, main, footer
- Skip link for keyboard users
- ARIA live region for announcements and flash messages
- Accessible dialog with focus trap, Escape handling, labeled by title, described by content, and focus return
- Jinja macros for accessible form inputs, radio groups, and alerts
- Form generator that supplies labels, hints, required markers, aria-describedby ties to hint and error IDs
- Validation with error messaging bound via aria-invalid and role="alert"
- Keyboard-visible focus and reduced-motion support
- Theme toggle with proper aria-pressed

Run
1. python -m venv .venv && . .venv/bin/activate
2. pip install -r requirements.txt
3. export FLASK_APP=app.py
4. flask run  # or: python app.py

Notes
- All components prefer native semantic HTML elements; ARIA is added only as necessary
- The modal uses a div with role=dialog and aria-modal=true for broad support
- The form is usable without JavaScript; only the dialog and theme toggle require JS

