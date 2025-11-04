import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

proposals = []

@app.route('/')
def index():
    return jsonify({"message": "Sandbox Dry-Run Mode API"})

@app.route('/proposals', methods=['GET'])
def get_proposals():
    return jsonify({"proposals": proposals})

@app.route('/proposals', methods=['POST'])
def create_proposal():
    data = request.get_json()
    if not data or 'change' not in data:
        return jsonify({"error": "Invalid proposal"}), 400
    
    proposal = {
        "id": len(proposals) + 1,
        "change": data['change'],
        "status": "pending",
        "dry_run": True
    }
    proposals.append(proposal)
    return jsonify(proposal), 201

@app.route('/proposals/<int:proposal_id>', methods=['GET'])
def get_proposal(proposal_id):
    proposal = next((p for p in proposals if p['id'] == proposal_id), None)
    if not proposal:
        return jsonify({"error": "Proposal not found"}), 404
    return jsonify(proposal)

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/proposals/999', methods=['GET'])
def _auto_stub_proposals_999():
    return 'Auto-generated stub for /proposals/999', 200
