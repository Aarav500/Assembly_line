import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from suggester.analyzer import FeatureDetector, AcceptanceTestDetector
from suggester.suggest import SuggestionEngine

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/suggest-missing-acceptance-tests")
def suggest_missing_acceptance_tests():
    try:
        payload = request.get_json(force=True, silent=True) or {}

        repo_path = payload.get("repo_path")
        features_input = payload.get("features")
        tests_input = payload.get("tests")
        options = payload.get("options") or {}

        feature_detector = FeatureDetector(options=options)
        test_detector = AcceptanceTestDetector(options=options)
        engine = SuggestionEngine(options=options)

        detected_features = []
        detected_tests = []

        if repo_path:
            try:
                if not os.path.isabs(repo_path):
                    repo_path = os.path.abspath(repo_path)
                if not os.path.exists(repo_path):
                    return jsonify({"error": f"repo_path not found: {repo_path}"}), 400
                detected_features = feature_detector.detect_features(repo_path)
                detected_tests = test_detector.detect_acceptance_tests(repo_path)
            except OSError as e:
                return jsonify({"error": f"File system error: {str(e)}"}), 500
            except Exception as e:
                return jsonify({"error": f"Error processing repository: {str(e)}"}), 500

        # Allow overrides/merges from payload
        try:
            if isinstance(features_input, list):
                detected_features = feature_detector.merge_features(detected_features, features_input)
            if isinstance(tests_input, list):
                detected_tests = test_detector.merge_tests(detected_tests, tests_input)
        except Exception as e:
            return jsonify({"error": f"Error merging features/tests: {str(e)}"}), 500

        try:
            suggestions = engine.suggest(detected_features, detected_tests)
            summary = engine.summary(suggestions, detected_features, detected_tests)
        except Exception as e:
            return jsonify({"error": f"Error generating suggestions: {str(e)}"}), 500

        return jsonify({
            "summary": summary,
            "features": detected_features,
            "tests": detected_tests,
            "suggestions": suggestions,
        })
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

if __name__ == "__main__":
    # For local dev only. In production, run via WSGI/ASGI server.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)



def create_app():
    return app