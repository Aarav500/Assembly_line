import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from maintenance.generator import MaintenanceGenerator, ValidationError

app = Flask(__name__)

generator = MaintenanceGenerator(base_output_dir=os.path.join(os.getcwd(), 'generated'))

@app.get('/health')
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + 'Z'})

@app.post('/generate')
def generate():
    try:
        cfg = request.get_json(force=True, silent=False)
        result = generator.generate(cfg)
        return jsonify({
            "job_name": result["job_name"],
            "output_dir": result["output_dir"],
            "files": result["files"],
        })
    except ValidationError as ve:
        return jsonify({"error": str(ve), "details": ve.details}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



def create_app():
    return app
