import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from pitch_generator import PitchGenerator
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

def _extract_payload(req):
    fields = [
        "project_name",
        "tagline",
        "problem",
        "solution",
        "target_users",
        "value_proposition",
        "market_size",
        "business_model",
        "traction",
        "competition",
        "differentiation",
        "go_to_market",
        "team",
        "roadmap",
        "ask",
        "contact",
        "tone"
    ]
    payload = {}
    for f in fields:
        payload[f] = request.form.get(f) if req == "form" else request.json.get(f)
    return payload

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"]) 
def generate():
    data = _extract_payload("form")
    missing = []
    for k in ["project_name", "problem", "solution"]:
        if not data.get(k):
            missing.append(k)
    if missing:
        flash("Missing required fields: " + ", ".join(missing))
        return redirect(url_for("index"))

    generator = PitchGenerator()
    result = generator.generate_all(data)

    return render_template(
        "result.html",
        data=data,
        elevator_pitch=result["elevator_pitch"],
        two_min_pitch=result["two_min_pitch"],
        one_pager=result["one_pager"],
        meta=result["meta"],
    )

@app.route("/api/generate", methods=["POST"]) 
def api_generate():
    if not request.is_json:
        return jsonify({"error": "Expected JSON body"}), 400
    data = _extract_payload("json")
    for k in ["project_name", "problem", "solution"]:
        if not data.get(k):
            return jsonify({"error": f"Missing required field: {k}"}), 400

    generator = PitchGenerator()
    result = generator.generate_all(data)
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app


@app.route('/generate-pitch', methods=['POST'])
def _auto_stub_generate_pitch():
    return 'Auto-generated stub for /generate-pitch', 200
