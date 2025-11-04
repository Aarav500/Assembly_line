import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
import logging
import time
from functools import wraps

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Metrics storage
metrics = {
    'requests': 0,
    'errors': 0,
    'latencies': []
}

def observe(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        metrics['requests'] += 1
        logger.info(f'Request to {f.__name__} started')
        
        try:
            result = f(*args, **kwargs)
            latency = time.time() - start_time
            metrics['latencies'].append(latency)
            logger.info(f'Request to {f.__name__} completed in {latency:.4f}s')
            return result
        except Exception as e:
            metrics['errors'] += 1
            logger.error(f'Error in {f.__name__}: {str(e)}')
            raise
    
    return decorated_function

@app.route('/')
@observe
def index():
    return jsonify({'message': 'Hello, World!', 'status': 'healthy'})

@app.route('/health')
@observe
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/metrics')
def get_metrics():
    avg_latency = sum(metrics['latencies']) / len(metrics['latencies']) if metrics['latencies'] else 0
    return jsonify({
        'total_requests': metrics['requests'],
        'total_errors': metrics['errors'],
        'average_latency': round(avg_latency, 4)
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
