import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import datetime
from flask import Flask, render_template, request, jsonify
from services.sources import search_all_sources
from services.brief import generate_research_brief

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/review', methods=['POST'])
def review():
    try:
        data = request.get_json(force=True)
        query = (data.get('query') or '').strip()
        if not query:
            return jsonify({"error": "Query is required"}), 400

        years_back = int(data.get('years_back') or 5)
        max_results = int(data.get('max_results') or 20)
        sources = data.get('sources') or ["crossref", "arxiv", "pubmed"]
        email = (data.get('email') or os.getenv('PUBMED_EMAIL') or '').strip()

        from_year = datetime.date.today().year - years_back

        papers, used_sources = search_all_sources(
            query=query,
            from_year=from_year,
            max_results=max_results,
            sources=sources,
            pubmed_email=email
        )

        brief = generate_research_brief(query=query, papers=papers)

        return jsonify({
            "query": query,
            "retrieved": len(papers),
            "sources_used": used_sources,
            "timeframe": f"from {from_year} to present",
            "papers": papers,
            "brief": brief
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/api/generate', methods=['POST'])
def _auto_stub_api_generate():
    return 'Auto-generated stub for /api/generate', 200
