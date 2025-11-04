import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import logging
import time
from functools import wraps
import json

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Metrics storage
metrics = {
    'request_count': 0,
    'request_duration': []
}

# Auto-instrumentation decorator
def instrument(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Trace ID generation
        trace_id = f"trace-{int(time.time() * 1000)}"
        
        # Start logging
        logger.info(f"[{trace_id}] Starting {func.__name__}")
        
        # Start timing
        start_time = time.time()
        
        # Increment metrics
        metrics['request_count'] += 1
        
        try:
            result = func(*args, **kwargs)
            
            # Calculate duration
            duration = time.time() - start_time
            metrics['request_duration'].append(duration)
            
            # Log success
            logger.info(f"[{trace_id}] Completed {func.__name__} in {duration:.4f}s")
            
            return result
        except Exception as e:
            # Log error
            logger.error(f"[{trace_id}] Error in {func.__name__}: {str(e)}")
            raise
    
    return wrapper

@app.route('/')
@instrument
def index():
    return jsonify({'message': 'Hello, World!'})

@app.route('/api/data', methods=['GET', 'POST'])
@instrument
def data():
    if request.method == 'POST':
        payload = request.get_json()
        logger.info(f"Received data: {json.dumps(payload)}")
        return jsonify({'status': 'success', 'data': payload}), 201
    return jsonify({'data': [1, 2, 3, 4, 5]})

@app.route('/metrics')
def get_metrics():
    avg_duration = sum(metrics['request_duration']) / len(metrics['request_duration']) if metrics['request_duration'] else 0
    return jsonify({
        'total_requests': metrics['request_count'],
        'average_duration': f"{avg_duration:.4f}s",
        'total_duration_samples': len(metrics['request_duration'])
    })

@app.route('/health')
@instrument
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
