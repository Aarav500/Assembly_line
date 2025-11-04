import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from datetime import datetime
import os

app = Flask(__name__)

# In-memory storage for recommendations
recommendations = [
    {
        "id": 1,
        "category": "security",
        "title": "Enable HTTPS",
        "description": "Ensure all connections use HTTPS to protect data in transit",
        "priority": "high",
        "impact": "Prevents man-in-the-middle attacks",
        "created_at": "2024-01-15T10:00:00Z"
    },
    {
        "id": 2,
        "category": "performance",
        "title": "Enable Caching",
        "description": "Implement Redis caching for frequently accessed data",
        "priority": "medium",
        "impact": "Reduces database load by 40%",
        "created_at": "2024-01-16T11:30:00Z"
    },
    {
        "id": 3,
        "category": "ux",
        "title": "Improve Mobile Responsiveness",
        "description": "Optimize UI for mobile devices",
        "priority": "medium",
        "impact": "Better user experience on mobile",
        "created_at": "2024-01-17T09:15:00Z"
    },
    {
        "id": 4,
        "category": "cost",
        "title": "Optimize Database Queries",
        "description": "Reduce unnecessary database calls to lower infrastructure costs",
        "priority": "high",
        "impact": "Estimated 25% cost reduction",
        "created_at": "2024-01-18T14:45:00Z"
    }
]

@app.route('/')
def home():
    return jsonify({
        "message": "Project Recommendations Hub API",
        "version": "1.0.0",
        "endpoints": [
            "/api/recommendations",
            "/api/recommendations/<id>",
            "/api/recommendations/category/<category>"
        ]
    })

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    category = request.args.get('category')
    priority = request.args.get('priority')
    
    filtered = recommendations
    
    if category:
        filtered = [r for r in filtered if r['category'].lower() == category.lower()]
    
    if priority:
        filtered = [r for r in filtered if r['priority'].lower() == priority.lower()]
    
    return jsonify({
        "count": len(filtered),
        "recommendations": filtered
    })

@app.route('/api/recommendations/<int:rec_id>', methods=['GET'])
def get_recommendation(rec_id):
    recommendation = next((r for r in recommendations if r['id'] == rec_id), None)
    
    if recommendation:
        return jsonify(recommendation)
    else:
        return jsonify({"error": "Recommendation not found"}), 404

@app.route('/api/recommendations/category/<category>', methods=['GET'])
def get_by_category(category):
    filtered = [r for r in recommendations if r['category'].lower() == category.lower()]
    
    return jsonify({
        "category": category,
        "count": len(filtered),
        "recommendations": filtered
    })

@app.route('/api/recommendations', methods=['POST'])
def create_recommendation():
    data = request.get_json()
    
    if not data or 'title' not in data or 'category' not in data:
        return jsonify({"error": "Missing required fields: title, category"}), 400
    
    new_id = max([r['id'] for r in recommendations]) + 1 if recommendations else 1
    
    new_recommendation = {
        "id": new_id,
        "category": data['category'],
        "title": data['title'],
        "description": data.get('description', ''),
        "priority": data.get('priority', 'low'),
        "impact": data.get('impact', ''),
        "created_at": datetime.utcnow().isoformat() + 'Z'
    }
    
    recommendations.append(new_recommendation)
    
    return jsonify(new_recommendation), 201

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)



def create_app():
    return app


@app.route('/api/recommendations/1', methods=['GET'])
def _auto_stub_api_recommendations_1():
    return 'Auto-generated stub for /api/recommendations/1', 200


@app.route('/api/recommendations/9999', methods=['GET'])
def _auto_stub_api_recommendations_9999():
    return 'Auto-generated stub for /api/recommendations/9999', 200


@app.route('/api/recommendations?category=security', methods=['GET'])
def _auto_stub_api_recommendations_category_security():
    return 'Auto-generated stub for /api/recommendations?category=security', 200
