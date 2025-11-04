Designer-friendly exports (Figma, Sketch, CSS tokens)

Quickstart:
- pip install -r requirements.txt
- export FIGMA_TOKEN=your_figma_pat  # optional; can also pass in request body
- python app.py

Endpoints:
- POST /api/figma/export { file_key, token?, prefix? }
- POST /api/sketch/export multipart/form-data (file=.sketch, prefix?)

Returns:
- tokens JSON (colors, typography)
- CSS variables (:root) and utility classes

Notes:
- Supports Figma solid color and text styles found via style references in the file.
- Supports Sketch color assets, shared layer style fills (solid), and shared text styles.

