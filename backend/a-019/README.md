License & SBOM Detector (Flask)

Overview:
- A minimal Flask application that scans Python dependencies for license information and generates a lightweight SPDX-like SBOM.
- Sources supported: currently installed environment, requirements.txt, pyproject.toml.

Endpoints:
- GET /               -> Minimal UI
- GET /api/packages   -> List packages with licenses (query: source=installed|requirements|pyproject, path=<file>)
- GET /api/licenses   -> License summary (same query params)
- GET /api/sbom       -> SBOM JSON (same query params)
- GET /download/sbom.json -> Download SBOM as file

Usage:
- Install deps: pip install -r requirements.txt
- Run: python app.py
- Visit: http://localhost:5000

Notes:
- License detection uses package metadata (License field, Trove classifiers), attempts to read LICENSE files from distributions, and falls back to PyPI JSON where necessary.
- SPDX IDs are heuristically inferred for common licenses (MIT, Apache-2.0, BSD variants, GPL/LGPL/AGPL, MPL, ISC). Unknowns will be marked as UNKNOWN.
- This is a best-effort tool; results may not be authoritative. Consider manual review for compliance-critical workflows.

