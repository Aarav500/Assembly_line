import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import logging

from services.news_service import get_news
from services.trends_service import get_trends
from services.signals_service import generate_signals
from config import SETTINGS


def create_app():
    app = Flask(__name__)
    CORS(app)

    logging.basicConfig(level=logging.INFO)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/health')
    def health():
        return jsonify({"status": "ok"})

    @app.route('/api/news')
    def api_news():
        query = request.args.get('query', default='market')
        lang = request.args.get('lang', default='en')
        country = request.args.get('country', default='US')
        days = int(request.args.get('days', default='7'))
        max_items = int(request.args.get('max_items', default='30'))
        news = get_news(query=query, lang=lang, country=country, days=days, max_items=max_items)
        return jsonify(news)

    @app.route('/api/trends')
    def api_trends():
        keywords_param = request.args.get('keywords', '')
        if not keywords_param:
            return jsonify({"error": "Missing keywords parameter"}), 400
        keywords = [k.strip() for k in keywords_param.split(',') if k.strip()]
        geo = request.args.get('geo', default='US')
        timeframe = request.args.get('timeframe', default='now 7-d')
        tz = int(request.args.get('tz', default='360'))
        data = get_trends(keywords=keywords, geo=geo, timeframe=timeframe, tz=tz)
        return jsonify(data)

    @app.route('/api/signals')
    def api_signals():
        keywords_param = request.args.get('keywords', '')
        if not keywords_param:
            return jsonify({"error": "Missing keywords parameter"}), 400
        keywords = [k.strip() for k in keywords_param.split(',') if k.strip()]
        geo = request.args.get('geo', default='US')
        timeframe = request.args.get('timeframe', default='now 7-d')
        lang = request.args.get('lang', default='en')
        country = request.args.get('country', default='US')
        days = int(request.args.get('days', default='7'))
        response = generate_signals(
            keywords=keywords,
            geo=geo,
            timeframe=timeframe,
            news_lang=lang,
            news_country=country,
            news_days=days
        )
        return jsonify(response)

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.exception("Unhandled exception: %s", e)
        return jsonify({"error": str(e)}), 500

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', SETTINGS['PORT']))
    debug = bool(int(os.environ.get('DEBUG', '0'))) if isinstance(SETTINGS['DEBUG'], bool) else SETTINGS['DEBUG']
    app.run(host='0.0.0.0', port=port, debug=debug)



@app.route('/api/trends?keyword=bitcoin', methods=['GET'])
def _auto_stub_api_trends_keyword_bitcoin():
    return 'Auto-generated stub for /api/trends?keyword=bitcoin', 200


@app.route('/api/news?topic=crypto', methods=['GET'])
def _auto_stub_api_news_topic_crypto():
    return 'Auto-generated stub for /api/news?topic=crypto', 200


@app.route('/api/signals?asset=ETH', methods=['GET'])
def _auto_stub_api_signals_asset_ETH():
    return 'Auto-generated stub for /api/signals?asset=ETH', 200


@app.route('/api/integrated', methods=['POST'])
def _auto_stub_api_integrated():
    return 'Auto-generated stub for /api/integrated', 200
