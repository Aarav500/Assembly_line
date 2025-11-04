import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
import json

app = Flask(__name__)

# Sample monetization models
MONETIZATION_MODELS = {
    'subscription': {'monthly_fee': 9.99, 'annual_fee': 99.99},
    'freemium': {'conversion_rate': 0.02, 'premium_fee': 14.99},
    'advertising': {'cpm': 5.0, 'ctr': 0.02},
    'transaction': {'commission_rate': 0.15}
}

@app.route('/')
def index():
    return jsonify({
        'message': 'Monetization Modeling and Revenue Projection API',
        'endpoints': {
            '/models': 'GET - List all monetization models',
            '/project': 'POST - Calculate revenue projection',
            '/compare': 'POST - Compare multiple scenarios'
        }
    })

@app.route('/models', methods=['GET'])
def get_models():
    return jsonify(MONETIZATION_MODELS)

@app.route('/project', methods=['POST'])
def project_revenue():
    data = request.get_json()
    model_type = data.get('model_type')
    users = data.get('users', 0)
    months = data.get('months', 12)
    
    if model_type not in MONETIZATION_MODELS:
        return jsonify({'error': 'Invalid model type'}), 400
    
    model = MONETIZATION_MODELS[model_type]
    revenue = 0
    
    if model_type == 'subscription':
        monthly_revenue = users * model['monthly_fee']
        revenue = monthly_revenue * months
    elif model_type == 'freemium':
        premium_users = users * model['conversion_rate']
        monthly_revenue = premium_users * model['premium_fee']
        revenue = monthly_revenue * months
    elif model_type == 'advertising':
        impressions = users * 100  # assume 100 page views per user per month
        monthly_revenue = (impressions / 1000) * model['cpm']
        revenue = monthly_revenue * months
    elif model_type == 'transaction':
        avg_transaction = data.get('avg_transaction', 100)
        transactions_per_user = data.get('transactions_per_user', 2)
        monthly_revenue = users * transactions_per_user * avg_transaction * model['commission_rate']
        revenue = monthly_revenue * months
    
    return jsonify({
        'model_type': model_type,
        'users': users,
        'months': months,
        'projected_revenue': round(revenue, 2),
        'monthly_average': round(revenue / months, 2)
    })

@app.route('/compare', methods=['POST'])
def compare_scenarios():
    data = request.get_json()
    scenarios = data.get('scenarios', [])
    results = []
    
    for scenario in scenarios:
        model_type = scenario.get('model_type')
        users = scenario.get('users', 0)
        months = scenario.get('months', 12)
        
        if model_type not in MONETIZATION_MODELS:
            continue
        
        model = MONETIZATION_MODELS[model_type]
        revenue = 0
        
        if model_type == 'subscription':
            monthly_revenue = users * model['monthly_fee']
            revenue = monthly_revenue * months
        elif model_type == 'freemium':
            premium_users = users * model['conversion_rate']
            monthly_revenue = premium_users * model['premium_fee']
            revenue = monthly_revenue * months
        elif model_type == 'advertising':
            impressions = users * 100
            monthly_revenue = (impressions / 1000) * model['cpm']
            revenue = monthly_revenue * months
        elif model_type == 'transaction':
            avg_transaction = scenario.get('avg_transaction', 100)
            transactions_per_user = scenario.get('transactions_per_user', 2)
            monthly_revenue = users * transactions_per_user * avg_transaction * model['commission_rate']
            revenue = monthly_revenue * months
        
        results.append({
            'model_type': model_type,
            'users': users,
            'projected_revenue': round(revenue, 2)
        })
    
    results.sort(key=lambda x: x['projected_revenue'], reverse=True)
    return jsonify({'scenarios': results})

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app
