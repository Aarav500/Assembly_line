import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import re

app = Flask(__name__)

TAXONOMIES = {
    'technology': ['ai', 'machine learning', 'python', 'javascript', 'cloud', 'database', 'api'],
    'business': ['marketing', 'sales', 'finance', 'strategy', 'management', 'startup'],
    'science': ['physics', 'chemistry', 'biology', 'research', 'experiment', 'data'],
    'health': ['medicine', 'fitness', 'nutrition', 'mental health', 'wellness', 'doctor']
}

def categorize_text(text):
    text_lower = text.lower()
    categories = {}
    
    for category, keywords in TAXONOMIES.items():
        matched_tags = []
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                matched_tags.append(keyword)
        
        if matched_tags:
            categories[category] = matched_tags
    
    return categories

@app.route('/')
def index():
    return jsonify({'message': 'Automatic Categorization API', 'endpoint': '/categorize'})

@app.route('/categorize', methods=['POST'])
def categorize():
    data = request.get_json()
    
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400
    
    text = data['text']
    categories = categorize_text(text)
    
    return jsonify({
        'text': text,
        'categories': categories,
        'total_categories': len(categories)
    })

@app.route('/taxonomies', methods=['GET'])
def get_taxonomies():
    return jsonify({'taxonomies': TAXONOMIES})

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app
