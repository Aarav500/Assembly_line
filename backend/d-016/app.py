import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Hello, World!"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/split/<int:total>/<int:index>')
def split_tests(total, index):
    """Simulate test splitting for CI parallelization"""
    tests = [f"test_{i}" for i in range(1, 21)]
    chunk_size = len(tests) // total
    remainder = len(tests) % total
    
    start = index * chunk_size + min(index, remainder)
    end = start + chunk_size + (1 if index < remainder else 0)
    
    split = tests[start:end]
    return jsonify({
        "total_splits": total,
        "split_index": index,
        "tests": split,
        "count": len(split)
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/split/4/0', methods=['GET'])
def _auto_stub_split_4_0():
    return 'Auto-generated stub for /split/4/0', 200
