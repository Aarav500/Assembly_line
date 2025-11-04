Integrated Design Inspector for Figma-to-code roundtrip

Quick start
- Create a Figma personal access token and set FIGMA_TOKEN in .env
- pip install -r requirements.txt
- python app.py
- Visit http://localhost:5000

Workflow
1) Upload your codebase as a zip. The server parses CSS variables, classes, and token JSON if present.
2) Enter a Figma file key. The server fetches styles metadata and samples values from nodes using those styles.
3) Get a report: matches, closest colors, text style similarity, and CSS variable suggestions.

Notes
- Figma color/text style values are inferred by scanning nodes that reference shared styles within the file.
- CSS parsing is heuristic (regex-based) for simplicity.

