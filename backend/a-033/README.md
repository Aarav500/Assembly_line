Project: Auto-detect feature flags & toggle them in the project manager UI

Stack: Python, Flask

How it works:
- The app scans your project for feature flag usage (e.g., is_enabled('flag') in Python or flag('flag') in Jinja templates).
- Detected flags are listed in the Feature Flags UI at /flags.
- You can toggle flags on/off; states persist in data/feature_flags.json.
- Click "Rescan project" to update the list after code changes.

Usage:
1) Install deps: pip install -r requirements.txt
2) Run: python app.py
3) Open: http://localhost:5000/flags

Flags in code:
- Python: from feature_flags import is_enabled
  if is_enabled('new_dashboard'):
      ...
  # Optional inline description: # FF: shown in the list

- Jinja: {% if flag('new_dashboard') %} ... {% endif %}
  Optional inline description: {# FF: description #}

Environment:
- Set FEATURE_SCAN_DIR to change the scanning root (defaults to project root).
- FEATURE_FLAGS_STORE is set by app to data/feature_flags.json.

Notes:
- Flags not found in last scan are marked as stale (but kept with their toggle state).
- You can use the Demo page at /demo to see flags in action (new_dashboard, beta_banner).

