Local Offline Analyzer (Privacy Mode)

Run simple CSV and text analysis fully offline using Flask. Privacy Mode blocks all outbound network connections, ensuring no cloud access.

Features
- Privacy Mode: network guard prevents external connections, server binds to localhost only
- CSV analysis: row/column counts, missing values, unique count (capped), top values, numeric stats (min/max/mean/median/stdev)
- Text analysis: lines, words, characters, average word length, top words
- Web UI and JSON API

Quickstart
1) Create and activate a venv (recommended)
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

2) Install dependencies
   pip install -r requirements.txt

3) Run the app
   python app.py

4) Open in your browser
   http://127.0.0.1:5000

Environment Variables
- PRIVACY_MODE=true|false  (default: true)
- SECRET_KEY=your-secret   (default: dev-secret-change-me)
- MAX_CONTENT_LENGTH=bytes (default: 10485760, i.e., 10MB)
- ALLOWED_EXTENSIONS=csv,txt  (default: csv,txt)

API
- POST /api/analyze  multipart/form-data with field "file"
  Returns JSON analysis result.

Notes
- Privacy Mode patches Python socket connections to allow only loopback (localhost/127.0.0.1/::1).
- Unique value counting for CSV is capped to avoid excessive memory usage.
- The server listens on 127.0.0.1 only.

Sample Data
- data/sample.csv
- data/sample.txt

