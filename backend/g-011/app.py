import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import make_classification
import shap

app = Flask(__name__)

# Train a simple model
X, y = make_classification(n_samples=100, n_features=4, random_state=42)
model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(X, y)

explainer = shap.TreeExplainer(model)

@app.route('/')
def home():
    return jsonify({"message": "Model Explainability Tools API"})

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    features = np.array(data['features']).reshape(1, -1)
    prediction = model.predict(features)[0]
    probability = model.predict_proba(features)[0].tolist()
    return jsonify({
        "prediction": int(prediction),
        "probability": probability
    })

@app.route('/explain', methods=['POST'])
def explain():
    data = request.json
    features = np.array(data['features']).reshape(1, -1)
    shap_values = explainer.shap_values(features)
    
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    
    return jsonify({
        "shap_values": shap_values[0].tolist(),
        "base_value": float(explainer.expected_value[1] if isinstance(explainer.expected_value, np.ndarray) else explainer.expected_value)
    })

@app.route('/counterfactual', methods=['POST'])
def counterfactual():
    data = request.json
    features = np.array(data['features'])
    target_class = data.get('target_class', 1)
    
    original_pred = model.predict(features.reshape(1, -1))[0]
    
    counterfactual_features = features.copy()
    for i in range(len(features)):
        for delta in [0.5, -0.5, 1.0, -1.0]:
            temp_features = counterfactual_features.copy()
            temp_features[i] += delta
            pred = model.predict(temp_features.reshape(1, -1))[0]
            if pred == target_class:
                counterfactual_features = temp_features
                break
        if model.predict(counterfactual_features.reshape(1, -1))[0] == target_class:
            break
    
    return jsonify({
        "original_prediction": int(original_pred),
        "counterfactual_features": counterfactual_features.tolist(),
        "counterfactual_prediction": int(model.predict(counterfactual_features.reshape(1, -1))[0]),
        "changes": (counterfactual_features - features).tolist()
    })

if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app
