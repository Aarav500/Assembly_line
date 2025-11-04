import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "Hello, World!"})

@app.route('/weather/<city>')
def weather(city):
    try:
        response = requests.get(f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid=demo', timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/users/<int:user_id>')
def get_user(user_id):
    try:
        response = requests.get(f'https://jsonplaceholder.typicode.com/users/{user_id}', timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
