import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

competitors = [
    {
        "id": 1,
        "name": "CompanyA",
        "market_share": 35,
        "features": ["feature1", "feature2", "feature3", "feature4"]
    },
    {
        "id": 2,
        "name": "CompanyB",
        "market_share": 28,
        "features": ["feature1", "feature3", "feature5"]
    },
    {
        "id": 3,
        "name": "CompanyC",
        "market_share": 22,
        "features": ["feature2", "feature4", "feature5", "feature6"]
    },
    {
        "id": 4,
        "name": "CompanyD",
        "market_share": 15,
        "features": ["feature1", "feature2", "feature6"]
    }
]

all_features = [
    {"name": "feature1", "description": "Advanced Analytics"},
    {"name": "feature2", "description": "Cloud Integration"},
    {"name": "feature3", "description": "Mobile App"},
    {"name": "feature4", "description": "API Access"},
    {"name": "feature5", "description": "AI-Powered Insights"},
    {"name": "feature6", "description": "Custom Reporting"}
]

@app.route('/')
def home():
    return jsonify({"message": "Competitive Landscape API"})

@app.route('/competitors', methods=['GET'])
def get_competitors():
    return jsonify({"competitors": competitors})

@app.route('/competitors/<int:competitor_id>', methods=['GET'])
def get_competitor(competitor_id):
    competitor = next((c for c in competitors if c['id'] == competitor_id), None)
    if competitor:
        return jsonify(competitor)
    return jsonify({"error": "Competitor not found"}), 404

@app.route('/features', methods=['GET'])
def get_features():
    return jsonify({"features": all_features})

@app.route('/feature-map', methods=['GET'])
def get_feature_map():
    feature_map = {}
    for feature in all_features:
        feature_name = feature['name']
        feature_map[feature_name] = {
            "description": feature['description'],
            "competitors": [c['name'] for c in competitors if feature_name in c['features']]
        }
    return jsonify({"feature_map": feature_map})

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app
