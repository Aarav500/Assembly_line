import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, redirect, url_for
from feature_registry import detect_features
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

@app.route("/")
def index():
    try:
        return redirect(url_for("feature_health"))
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/features")
def feature_health():
    try:
        features = detect_features()
        return render_template("health_matrix.html", features=features)
    except Exception as e:
        logger.error(f"Error in feature_health route: {str(e)}")
        return jsonify({"error": "Failed to load feature health matrix"}), 500

@app.route("/api/features")
def api_features():
    try:
        features = detect_features()
        return jsonify({
            "features": features,
            "summary": {
                "functional": sum(1 for f in features if f["status"] == "functional"),
                "missing_tests": sum(1 for f in features if f["status"] == "missing_tests"),
                "broken": sum(1 for f in features if f["status"] == "broken"),
                "total": len(features),
            }
        })
    except Exception as e:
        logger.error(f"Error in api_features route: {str(e)}")
        return jsonify({"error": "Failed to retrieve features"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

def create_app():
    return app